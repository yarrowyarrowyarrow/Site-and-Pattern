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

**What is on is a row of chips (F194, V3.01)**, one per filter, each removing
its own: "Type: Tree or Shrub ×". A dropdown reads its dimension once chosen
and opens on a line saying how its values combine. An empty result names the
restriction that emptied it, with what removing it would bring back. And the
site's soil pH, a filter the app has set since V1.67 that nothing showed, is a
chip and a toggle like any other.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListView,
    QPushButton, QVBoxLayout, QWidget,
)

from src import plant_filters as pf
from src.filter_status import DIM as _DIM, FilterLine, WhyEmpty, wrapped
from src.filter_widgets import (
    COMBO_STYLE, CheckableComboBox, build_ecoregion_tree,
)
from src.flow_layout import FlowLayout
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
_SEARCH = ("QLineEdit { background: #16241a; border: 1px solid #2e4a2e; "
           "border-radius: 4px; padding: 5px 8px; color: #c8e6c9; "
           "font-size: 13px; }"
           "QLineEdit:focus { border: 2px solid #ffe082; }")


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
        self._rows: list = []
        # The site's soil pH (V1.67), set by the app; on until the reader
        # takes it off, and then off for the session (V3.01).
        self._soil_ph: Optional[float] = None
        self._soil_off = False
        self._soil_hidden = 0
        self._catalogue: Optional[int] = None
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
            self.order_combo.setItemData(self.order_combo.count() - 1,
                                         wrapped(tip),
                                         Qt.ItemDataRole.ToolTipRole)
        self.order_combo.setStyleSheet(COMBO_STYLE)
        self._sync_order_combo()
        self.order_combo.activated.connect(self._on_order_chosen)
        count_row.addWidget(self.order_combo)
        col.addLayout(count_row)

        # Said in place of an empty list's silence: which restriction emptied
        # it, and what removing it would bring back.
        self.why_empty = WhyEmpty()
        self.why_empty.remove_requested.connect(self._take_offer)
        self.why_empty.clear_requested.connect(lambda: self._take_offer(None))
        col.addWidget(self.why_empty)

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
        self.filter_line = FilterLine()
        self.filters_button = self.filter_line.filters_button
        self.clear_button = self.filter_line.clear_button
        self.none_label = self.filter_line.none_label
        self.filters_button.toggled.connect(self.set_filters_open)
        self.filter_line.remove_requested.connect(self.remove)
        self.filter_line.clear_requested.connect(self.clear_filters)
        col.addWidget(self.filter_line)

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
            combo.set_checked_keys([str(v) for v in
                                    (self._criteria.get(f.key) or [])])
            combo.selectionChanged.connect(
                lambda k=f.key: self._on_facet(k))
            grid.addWidget(combo, i // per_row, i % per_row)
            self.combos[f.key] = combo
        area.addLayout(grid)

        chips = QWidget()
        flow = FlowLayout(chips, h_spacing=4, v_spacing=4)
        flow.setContentsMargins(0, 0, 0, 0)
        self.chips: dict = {}
        for q in pf.QUALITIES:
            btn = QPushButton(q.label)
            btn.setCheckable(True)
            btn.setChecked(bool(self._criteria.get(q.key)))
            btn.setToolTip(wrapped(q.tip))
            btn.setAccessibleDescription(q.tip)
            btn.setStyleSheet(_CHIP_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.toggled.connect(lambda _on, k=q.key: self._on_quality(k))
            flow.addWidget(btn)
            self.chips[q.key] = btn
        # The site's soil pH, beside the qualities and drawn like them, so a
        # filter the app switched on can be switched back on once taken off.
        self.soil_toggle = QPushButton("")
        self.soil_toggle.setCheckable(True)
        self.soil_toggle.setStyleSheet(_CHIP_STYLE)
        self.soil_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.soil_toggle.toggled.connect(self.set_soil_on)
        self.soil_toggle.hide()
        flow.addWidget(self.soil_toggle)
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

    def _refresh_chips(self):
        """One chip per restriction that is on, the soil pH among them."""
        entries = [(k, w) for k, w in pf.filters_on(self._criteria)
                   if k != "query"]
        tips = {}
        if self.soil_applies():
            entries.append(("soil", pf.soil_label(self._soil_ph)))
            tips["soil"] = (pf.soil_tip(self._soil_ph, self._soil_hidden)
                            + " Click to remove it.")
        self.filter_line.set_entries(entries, tips)

    def chip_texts(self) -> list:
        """The words on the chips, without their ×: what is on, as drawn."""
        return self.filter_line.texts()

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
        """Take off everything the chips show. The soil pH too: a "Clear all"
        that left the app's own filter on would leave the reader looking at
        fewer plants than the catalogue holds with nothing to say why."""
        query = self._criteria.get("query") or ""
        if self.soil_applies():
            self._soil_off = True
            self._sync_soil_toggle()
        self.set_criteria({"query": query} if query else {})
        self.criteria_changed.emit(self.criteria())

    def remove(self, key: str):
        """Take one restriction off: a facet, a quality, the search text or
        ``"soil"``. What a chip and the empty state's buttons do."""
        if key == "soil":
            self.set_soil_on(False)
            return
        if key == "query":
            self.search_box.setText("")
            self.refresh()
        elif key in self.combos:
            self.combos[key].set_checked_keys([])
            self._criteria[key] = []
            self.refresh()
        elif key in self.chips:
            self.chips[key].setChecked(False)       # its toggled signal searches
            return
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

    # ── The site's soil pH ──────────────────────────────────────────────────

    def set_soil_ph(self, ph: Optional[float]):
        """The site's soil pH, or ``None`` for no site. The app sets it when a
        pin's soil arrives and when a project loads; it filters until the reader
        takes it off, which then holds for the session, so a soil re-fetch does
        not quietly put it back."""
        ph = float(ph) if isinstance(ph, (int, float)) else None
        if ph == self._soil_ph:
            return
        self._soil_ph = ph
        self._sync_soil_toggle()
        self.refresh()

    def soil_ph(self) -> Optional[float]:
        return self._soil_ph

    def soil_applies(self) -> bool:
        return self._soil_ph is not None and not self._soil_off

    def set_soil_on(self, on: bool):
        on = bool(on)
        if on == (not self._soil_off):
            self._sync_soil_toggle()
            return
        self._soil_off = not on
        self._sync_soil_toggle()
        if self._soil_ph is not None:
            self.refresh()

    def _sync_soil_toggle(self):
        btn = self.soil_toggle
        btn.setVisible(self._soil_ph is not None)
        if self._soil_ph is None:
            return
        btn.blockSignals(True)
        btn.setChecked(self.soil_applies())
        btn.blockSignals(False)
        btn.setText(pf.soil_label(self._soil_ph))
        tip = pf.soil_tip(self._soil_ph, self._soil_hidden
                          if self.soil_applies() else None)
        btn.setToolTip(wrapped(tip))
        btn.setAccessibleDescription(tip)

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
                    item.setToolTip(wrapped(
                        "Drop a pin on your site to rank plants by what has "
                        "been recorded near it."))
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

    def _search(self, criteria: dict, *, soil: bool) -> list:
        search_fn = self._search_fn
        if search_fn is None:
            from src.db.plants import search_plants as search_fn
        kwargs = pf.criteria_to_kwargs(criteria)
        if soil and self._soil_ph is not None:
            kwargs["soil_ph"] = self._soil_ph
        return search_fn(**kwargs)

    def refresh(self):
        """Run the search now and show the result. Reads the search box, so a
        refresh straight after typing does not wait for the debounce."""
        self._search_timer.stop()
        self._criteria["query"] = self.search_box.text()
        soil = self.soil_applies()
        try:
            rows = self._search(self._criteria, soil=soil)
            # What the soil pH alone is hiding, for its chip: the plants the
            # reader's own filters would show without it.
            self._soil_hidden = (len(self._search(self._criteria, soil=False))
                                 - len(rows)) if soil else 0
        except Exception as exc:                                # noqa: BLE001
            self.count_label.setText(f"Search failed: {exc}")
            return
        self._rows = self._ordered(rows)
        self.model.set_plants(self._rows)
        n = len(self._rows)
        restricted = bool(pf.filters_on(self._criteria)) or soil
        if not restricted:
            self._catalogue = n
        self._refresh_chips()
        self._sync_soil_toggle()
        if not n:
            self.count_label.setText("No plants match")
        elif restricted and self._catalogue_size():
            self.count_label.setText(f"{n} of {self._catalogue} plants")
        else:
            self.count_label.setText(f"{n} plant{'s' if n != 1 else ''}")
        self._show_why_empty(restricted and not n)
        self.results_changed.emit()

    def _catalogue_size(self) -> Optional[int]:
        """How many plants nothing restricts, for "319 of 424". Counted once;
        refreshed whenever an unrestricted search runs anyway."""
        if self._catalogue is None:
            try:
                self._catalogue = len(self._search({}, soil=False))
            except Exception:                                   # noqa: BLE001
                return None
        return self._catalogue

    def _show_why_empty(self, empty: bool):
        """Name what emptied the list (``plant_filters.what_emptied``). Runs
        only on an empty list, and then at most nineteen searches."""
        if not empty:
            self.why_empty.dismiss()
            return
        soil = self.soil_applies()
        self.why_empty.explain(*pf.what_emptied(
            self._criteria,
            lambda criteria, on: len(self._search(criteria, soil=on)),
            soil=pf.soil_label(self._soil_ph) if soil else None),
            tab_between=(self.order_combo, self.view))

    def _take_offer(self, key: Optional[str]):
        """An empty state's offer, taken. The button goes with the empty state,
        and Qt would hand the keyboard on to the map's toolbar: give it to the
        plants that came back, or to the next offer if there are still none."""
        had = self.why_empty.has_keyboard()
        if key is None:
            self.clear_filters()
        else:
            self.remove(key)
        if had:
            offers = self.why_empty.buttons()
            target = (offers[0] if offers and not self.why_empty.isHidden()
                      else self.view if self._rows else self.search_box)
            target.setFocus(Qt.FocusReason.OtherFocusReason)

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
