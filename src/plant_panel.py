"""
plant_panel.py — the Plants → Browse tab: the plant picker, Place, and the mix.

The search, filters, order and list are ``src/plant_picker.py``, the same
widget the Plant Directory and the community builder show (F192, V3.00). A
plant's page opens beside the list (``src/species_flyout.py``); this panel says
when, through ``page_requested`` and ``page_closed``. What it keeps is placing:
the Place button and the list's gestures (``src/place_action.py``), what is
armed apart from what is looked at, and the mix.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QSizePolicy, QScrollArea, QGroupBox, QSpinBox,
    QColorDialog, QMenu,
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QModelIndex,
)
from PyQt6.QtGui import QColor

# The list, its model and the vocabulary every picker shares (V3.00: the
# search, filters and order are src/plant_picker.py). Some names are imported
# for other modules that have always found them here.
from src.plant_list_view import (  # noqa: F401  (re-exports)
    PlantListModel,
    PlantRowDelegate,
    _TYPE_COLORS,
    _SUN_LABELS,
    _USE_LABELS,
    _WATER_LABELS,
    _AVAILABILITY_LABELS,
    _PLANT_OBJ_ROLE,
    _PLANT_MIME,
)
from src.filter_widgets import CheckableComboBox  # noqa: F401  (re-export)
from src.plant_facets import (  # noqa: E402,F401  (re-export, not a use)
    _TYPE_LABELS, _DECIDUOUS_LABELS, _LIFECYCLE_LABELS, _MONTH_LABELS,
    _ECOREGION_CHOICES, _ECOREGION_DISPLAY, _AB_ECOREGION_CHOICES,
)


# Mix rows shown before they scroll (V2.98; the community mix's number).
_MIX_ROWS_VISIBLE = 4


class _MixDropGroupBox(QGroupBox):
    """The 'Plant current mix' box, made a drop target so plants can be dragged
    from the results list straight into the mix (V1.87). ``on_drop`` receives
    the dropped plant's id."""

    def __init__(self, title: str, on_drop, parent=None):
        super().__init__(title, parent)
        self._on_drop = on_drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(_PLANT_MIME):
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(_PLANT_MIME):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasFormat(_PLANT_MIME):
            try:
                pid = int(bytes(e.mimeData().data(_PLANT_MIME)).decode())
            except (ValueError, TypeError):
                return
            self._on_drop(pid)
            e.acceptProposedAction()
        else:
            super().dropEvent(e)


# ── Main widget ───────────────────────────────────────────────────────────────

class PlantPanel(QWidget):
    """Right-hand panel for browsing, filtering and placing plants."""

    # Place a plant (or pattern of plants). The third arg is the legacy
    # quantity spinner value (used when pattern["kind"]=="single"); the
    # fourth is the pattern descriptor — see MapWidget.set_mode docstring.
    place_plant_requested = pyqtSignal(int, str, int, dict)   # plant_id, common_name, quantity, pattern
    placement_cancelled = pyqtSignal()                        # nothing left to place (V2.37)
    # What the map is armed with, for the placement bar over it (V2.98):
    # {"armed", "what", "kind", "qty", "mix"}. See src/placement_bar_flow.py.
    armed_changed = pyqtSignal(dict)
    fill_area_requested = pyqtSignal(object, float, str, bool)  # members [(pid,weight)], spacing_m, name, matrix (F3/F22)
    color_changed = pyqtSignal(int, str)                       # plant_id, hex_color
    # Emitted when "Save as Plant Community" creates a new community from
    # the stack, so the Communities tab can refresh its library list.
    communityCreated = pyqtSignal()
    # Emitted whenever _placed_counts mutates (place / clear / load / remove)
    # so the sibling On-This-Design inner tab can refresh its Plants sub-tab.
    placed_counts_changed = pyqtSignal()
    # A plant's page, beside the list (V3.00, src/species_flyout.py):
    # {"plant", "placed", "in_mix", "focus"}; page_closed puts it away.
    page_requested = pyqtSignal(dict)
    page_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_zone: Optional[int] = None
        self._selected_plant: Optional[dict] = None
        self._placed_counts: dict[int, int] = {}   # plant_id -> count
        self._soil_ph: Optional[float] = None       # from site data (V1.67)

        # Polyculture mix — explicit list of species the user has added
        # via right-click → "Add to Polyculture Mix". When ≥2 species
        # are present, Row/Grid/Circle placements distribute species
        # across positions; otherwise the placement is single-species
        # (the currently-selected plant). The mix is intentionally
        # independent of the current selection — the selection only
        # exists to drive the Place button and detail expansion.
        self._mix_species: list[dict] = []
        self._MIX_MAX = 8   # cap so the list stays readable in the panel

        # Most recent recipe stashed at Place-click time so App can
        # consume it when JS fires onPatternPlaced after the user's
        # 2-click gesture (otherwise changing the mix mid-gesture would
        # use the wrong recipe). Cleared after consumption.
        self._pending_polyculture: Optional[dict] = None

        # True while the map is armed to place what this panel has selected.
        # MainWindow calls set_armed(False) when placement ends (Esc, another
        # tool), so the bar can never claim the map is listening when it isn't.
        self._armed = False
        # What was armed, captured at arming time: the bar describes what the
        # map holds, which is not always what the list shows selected now.
        self._armed_what = ""
        # What is being placed, apart from what is being looked at (V2.99):
        # the plant a Place action named, or the mix after Place mix. A
        # pattern says only how; it never swaps one for the other.
        self._armed_plant: Optional[dict] = None
        self._armed_mix = False

        from src.placement_arming import rearm_timer
        self._rearm_timer = rearm_timer(self, self._rearm)

        # The plant whose page is open beside the list, or 0 (V3.00).
        self._page_id = 0
        self._page_plant: dict = {}
        # Where the site is, asked when the list is ordered: MainWindow hands
        # in SitePanel.current_coords. See _check_site.
        self._site_source = None

        self._build_ui()
        # A count changing under an open page (undo, a delete) redraws it.
        self.placed_counts_changed.connect(self._refresh_page)

        # The ecoregion picker starts on its "Restoring toward…" placeholder
        # (V1.87): nothing is pre-selected, and it's no longer restored from a
        # sticky cross-session QSettings value. A property pin dropped *this
        # session* drives it live via set_autodetected_ecoregion (wired in
        # app.py from SitePanel.ecoregion_detected).

        self._run_search()   # populate on startup

    def set_autodetected_ecoregion(self, key):
        """Live update from a property pin dropped this session (V1.87).

        ``key`` is the detected ecoregion id, or a *list* of them since V2.38 —
        a site near a boundary is in more than one, and checking both is the
        difference between seeing that region's species and not. ``""``/``None``
        /``[]`` clears it (pin removed, or outside known regions).

        Session-only: nothing is persisted, so a region never carries over to
        an unrelated later session. Setting it silently (no
        ``_on_ecoregion_changed``) then re-running the search keeps the list in
        sync without a double query."""
        if isinstance(key, (list, tuple, set)):
            keys = [k for k in key if k]
        else:
            keys = [key] if key else []
        self._check_site()
        self.picker.set_facet("ecoregion", keys)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # One column that scrolls when it cannot fit, rather than squeezing
        # its sections into each other (V2.98, src/scroll_column.py).
        from src.scroll_column import scroll_column
        root = scroll_column(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._root_layout = root

        # Browser (top, stretches to fill) + the mix strip (bottom, its own
        # height). The placement settings are not in this column since V2.98:
        # they are built here and shown in the bar over the map while placing.

        # ── Top pane: header, then the picker every plant list shares ─────
        local_tab = QWidget()
        top_layout = QVBoxLayout(local_tab)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(4)

        # Page header (V1.86) — a plain, non-collapsible title that mirrors the
        # Plant Community Library page.
        title_label = QLabel(
            "<b>Plant Library</b>  "
            "<span style='color:#90a4ae;font-weight:normal;'>(browse &amp; place)</span>"
        )
        title_label.setStyleSheet("font-size: 13px;")
        top_layout.addWidget(title_label)

        # Search, filters, order and the list (V3.00, src/plant_picker.py):
        # the same widget the Plant Directory and the community builder show,
        # over one vocabulary. Its filters start folded to the line that says
        # which are on; eighteen do not fit above a list in this column.
        from src.plant_picker import PlantPicker
        self.picker = PlantPicker(self, draggable=True)
        self.picker.results_changed.connect(self._on_results)
        self._results_list = self.picker.view
        self._results_model = self.picker.model
        self._search_box = self.picker.search_box
        self._results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._results_list.customContextMenuRequested.connect(self._on_plant_context_menu)
        # Selecting is looking (V2.99): it names the plant on the Place button
        # and, since V3.00, shows its page beside the list. Enter, a
        # double-click, the button or the context menu place it; see
        # src/place_action.py.
        self._results_list.selectionModel().selectionChanged.connect(
            self._on_selection_changed)
        from src.place_action import ListGestures, PlaceButton
        gestures = ListGestures(self._results_list, read_key=True)
        gestures.place.connect(self._on_list_place)
        gestures.choose.connect(self._on_list_choose)
        gestures.read.connect(self._on_list_read)
        top_layout.addWidget(self.picker, 1)
        self._place_btn = PlaceButton("plant")
        self._place_btn.clicked.connect(
            lambda: self._place_plant(self._selected_plant))
        top_layout.addWidget(self._place_btn)

        # The browser pane is no longer collapsible (V1.86): collapsing it
        # revealed nothing useful and only confused users. The "Plant Library"
        # header sits inline at the top of the pane (added above).
        root.addWidget(local_tab, 1)   # stretches to fill the sidebar

        # ── Placement settings: built here, shown in the bar over the map ───
        # Until V2.98 these filled a collapsible "Placement" section below the
        # list, in a column that does not scroll: opening it took the list's
        # height and squeezed the pattern buttons to 11 px (0 px at 1366 × 768).
        # The bar adopts them (src/placement_bar_flow.py); until then they have
        # no parent, so they never float over this panel.
        from src.placement_controls import PlacementControlsWidget, labelled_unit
        self._placement = PlacementControlsWidget(show_canopy_base=True)
        self._placement.patternKindChanged.connect(self._on_pattern_kind_changed)
        self._placement.patternChanged.connect(self._on_pattern_params_changed)

        # Qty is a Single-mode burst. It stayed on screen in Row/Grid/Circle,
        # where its own tooltip said it was ignored; now it shows for Single only.
        self._qty_spin = QSpinBox()
        self._qty_spin.setRange(1, 50)
        self._qty_spin.setValue(1)
        self._qty_spin.setFixedWidth(64)
        self._qty_spin.setToolTip("How many to place at each click, as a cluster")
        self._qty_spin.valueChanged.connect(self._on_pattern_params_changed)
        self._placement.add_extra(
            labelled_unit("Qty", self._qty_spin, "Quantity"), ("single",))

        # This species' marker colour on the map. It sits on the bar's first
        # line, beside the name it applies to, and hides while a mix is placed
        # (each mix row has its own dot).
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(26, 26)
        self._color_btn.setToolTip("Set a custom marker colour for this plant")
        self._color_btn.clicked.connect(self._on_color_pick)
        self._color_unit = labelled_unit("Colour", self._color_btn, "Marker colour")
        self._update_color_btn("")

        # ── The mix: stays beside the list it is built from ───────────────
        # Plants are dragged into it from the list, so it cannot live in a bar
        # that only exists while placing. Its *placement* moved: Place mix arms
        # it, and the bar takes it from there.
        self._build_polyculture_controls(root)

    # ── Search ────────────────────────────────────────────────────────────────

    def set_soil_ph(self, ph):
        """Set the site's soil pH (from site data) so the browser only shows
        plants tolerant of it. ``None`` clears the constraint (V1.67)."""
        new = float(ph) if isinstance(ph, (int, float)) else None
        if new == self._soil_ph:
            return
        self._soil_ph = new
        self._check_site()
        self.picker.set_extra(soil_ph=new)

    def set_site_source(self, source):
        """``source()`` → ``(lat, lng)`` or ``None``: where the design is, for
        the "Recorded near this site" order. Read, not pushed, because a project load
        restores the pin without any of the signals a dropped pin sends."""
        self._site_source = source
        self._check_site()

    def _check_site(self):
        """Hand the picker the site as it is now. Called whenever the site
        could have changed under the list: a pin's region arriving, the zone,
        the soil pH, and the tab being shown."""
        coords = None
        if self._site_source is not None:
            try:
                coords = self._site_source()
            except Exception:                                   # noqa: BLE001
                coords = None
        self.picker.set_site(coords, self._current_zone)

    def _run_search(self):
        self.picker.refresh()

    def _on_results(self):
        """A search ran or the order changed: the counts ride along, the
        highlight follows the plant being looked at, and its page closes if
        the search hid it."""
        self._results_model.set_placed_counts(self._placed_counts)
        plants = self.picker.rows()
        self._reselect(plants)
        if self._page_id and not any(p.get("id") == self._page_id
                                     for p in plants):
            self.close_page()

    # ── Looking and placing ───────────────────────────────────────────────────

    def _on_selection_changed(self, *_):
        """The highlighted row is what the Place button names, and that is all.

        From V2.37 selecting armed the map (a tester kept planting "the last
        thing"), so every way of looking did, down to keyboard focus arriving
        in the list, which armed its first plant. Choosing while the map is
        placing still switches it: see :meth:`_on_list_choose`.
        """
        rows = self._results_list.selectionModel().selectedIndexes()
        plant = rows[0].data(_PLANT_OBJ_ROLE) if rows else None
        self._selected_plant = plant or None
        self._place_btn.set_subject((plant or {}).get("common_name", ""))

    def _reselect(self, plants):
        """A search resets the list and drops its highlight: put it back on the
        plant being looked at, or let go if the search hid it, so the Place
        button never names a plant that is not on screen."""
        pid = (self._selected_plant or {}).get("id")
        row = next((i for i, p in enumerate(plants)
                    if pid and p.get("id") == pid), -1)
        if row >= 0:
            self._results_list.setCurrentIndex(self._results_model.index(row))
        else:
            self._on_selection_changed()

    def _on_list_place(self, index: QModelIndex):
        """Enter or a double-click on a row: place that plant."""
        plant = index.data(_PLANT_OBJ_ROLE)
        if plant:
            self._results_list.setCurrentIndex(index)
            self._place_plant(plant)

    def _on_list_choose(self, index: QModelIndex):
        """A finished click or an arrow key onto a row shows its page (V3.00).
        While the map is placing, the list is a palette instead: what you
        choose is what the next click plants, so "the last thing" is never
        placed by mistake, and the page stays shut so the map stays clear."""
        plant = index.data(_PLANT_OBJ_ROLE)
        if not plant:
            return
        if not self._armed:
            self._show_page(plant)
        elif self._armed_mix or plant.get("id") != (
                self._armed_plant or {}).get("id"):
            self._place_plant(plant)

    def _on_list_read(self, index: QModelIndex):
        """→ on a row: its page, with the keyboard in it (Esc comes back)."""
        plant = index.data(_PLANT_OBJ_ROLE)
        if plant and not self._armed:
            self._show_page(plant, focus=True)

    # ── The page beside the list (V3.00) ─────────────────────────────────────

    def _show_page(self, plant: dict, *, focus: bool = False):
        pid = int(plant.get("id") or 0)
        if not pid:
            return
        self._page_id = pid
        self._page_plant = plant
        self.page_requested.emit({
            "plant": plant, "placed": self.placed_count(pid),
            "in_mix": self.in_mix(pid), "focus": focus})

    def _refresh_page(self):
        """The page is open and its plant's count or mix state changed."""
        if self._page_id:
            self._show_page(self._page_plant)

    def close_page(self):
        if self._page_id:
            self._page_id = 0
            self.page_closed.emit()

    def page_plant_id(self) -> int:
        return self._page_id

    def focus_list(self):
        self._results_list.setFocus(Qt.FocusReason.OtherFocusReason)

    def placed_count(self, plant_id) -> int:
        return int(self._placed_counts.get(plant_id, 0))

    def in_mix(self, plant_id) -> bool:
        return any(s.get("id") == plant_id for s in self._mix_species)

    def add_to_mix(self, plant: dict):
        """Add to the mix from outside the list: the page's Add to mix."""
        self._add_to_mix(plant)

    def place_from_elsewhere(self, plant: dict):
        """Place ``plant``, named somewhere other than this list: the page
        beside it, or the Plant Directory. It is highlighted here first when
        the list shows it, so the Place button and the bar agree."""
        if plant and plant.get("id"):
            self.picker.select_plant_id(plant.get("id"))
            self._place_plant(plant)

    def hideEvent(self, event):
        # The page belongs to this tab: switching tab, or folding the side
        # panel away, puts it away too.
        self.close_page()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._check_site()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._page_id:
            self.close_page()
            event.accept()
            return
        super().keyPressEvent(event)

    def _place_plant(self, plant):
        """A Place action named ``plant``: arm the map with it, in the bar's
        pattern. Its colour and its fill spacing come in with it."""
        if not plant or not plant.get("id"):
            return
        if self._armed_mix or plant.get("id") != (self._armed_plant or {}).get("id"):
            self._armed_mix = False
            self._armed_plant = plant
            self._update_color_btn(plant.get("marker_color") or "")
            self._sync_fill_spacing()
        self._on_place_clicked()

    # ── Arming ────────────────────────────────────────────────────────────────

    def _on_pattern_params_changed(self):
        from src.placement_arming import request_rearm
        request_rearm(self)

    def _rearm(self):
        """The debounce fired: re-arm what is armed with the settings as they
        are now, unless the map stood down in the meantime."""
        if self._armed:
            self._on_place_clicked()

    def set_armed(self, armed: bool):
        """Told by MainWindow when placement mode ends (Esc, another tool)."""
        if not armed:
            self._rearm_timer.stop()
        if self._armed == bool(armed):
            return
        self._armed = bool(armed)
        if not armed:
            self._armed_mix = False
        self._announce_armed()

    def _announce_armed(self):
        """Tell the placement bar what the map holds (or that it holds nothing).
        Placing puts the page away: the map has to be clear for the click."""
        if self._armed:
            self.close_page()
        self._color_unit.setVisible(not self._armed_mix)
        self.armed_changed.emit({
            "armed": self._armed,
            "what": self._armed_what,
            "kind": self._placement.kind,
            "qty": self._qty_spin.value(),
            "mix": len(self._mix_species) if self._armed_mix else 0,
        })

    def placement_controls(self):
        """The pattern controls, for the placement bar to adopt (V2.98)."""
        return self._placement

    def placement_accessory(self):
        """The marker colour, for the bar's first line (V2.98)."""
        return self._color_unit

    # ── Fill an area with plants (Placement Mode → Fill Area) ───────────────────

    def _fill_members(self):
        """``(members, name)`` for an area fill of what is being placed: the
        mix after Place mix, else the plant. ``members`` is a list of
        ``(plant_id, weight)``."""
        if self._armed_mix and len(self._mix_species) >= 2:
            members = [(int(s["id"]), float(s.get("_weight", 1) or 1))
                       for s in self._mix_species if s.get("id")]
            return members, "Custom mix"
        plant = self._armed_plant or {}
        if plant.get("id"):
            return [(int(plant["id"]), 1.0)], plant.get("common_name", "")
        return [], ""

    def selected_plant(self) -> Optional[dict]:
        """The species currently selected here, or ``None``.

        Public since V2.46 so the 3D preview can plant *the same* selection the
        map's Place button uses, rather than carrying a second species picker
        that could disagree with this one.
        """
        return self._selected_plant

    # ── Place on map ──────────────────────────────────────────────────────────

    # ── Pattern mode UI ───────────────────────────────────────────────────────

    def _build_polyculture_controls(self, outer: QVBoxLayout):
        """Build the mix strip under the list: a drop target, its rows (four
        visible, the rest scroll), and its actions, Place mix first."""
        mix_box = _MixDropGroupBox("Plant current mix", self._add_to_mix_by_id)
        mix_box.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        ml = QVBoxLayout(mix_box)
        ml.setContentsMargins(6, 6, 6, 6)
        ml.setSpacing(3)

        self._mix_status = QLabel("Drag or right-click plants here to build a mix.")
        self._mix_status.setWordWrap(True)
        self._mix_status.setStyleSheet("color: #78909c; font-size: 10px;")
        ml.addWidget(self._mix_status)

        # ── Species rows (one per mix entry, custom widgets) ─────────
        self._mix_rows_container = QWidget()
        self._mix_rows_layout = QVBoxLayout(self._mix_rows_container)
        self._mix_rows_layout.setContentsMargins(0, 2, 0, 2)
        self._mix_rows_layout.setSpacing(2)
        # Four rows show and the rest scroll, as in the community mix: a full
        # mix otherwise takes its whole height out of the list above.
        self._mix_rows_scroll = QScrollArea()
        self._mix_rows_scroll.setWidgetResizable(True)
        self._mix_rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._mix_rows_scroll.setWidget(self._mix_rows_container)
        self._mix_rows_scroll.setMaximumHeight(_MIX_ROWS_VISIBLE * 26 + 8)
        self._mix_rows_scroll.setVisible(False)
        ml.addWidget(self._mix_rows_scroll)

        # ── Actions: place it, clear it, keep it ─────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._mix_place_btn = QPushButton("Place mix")
        self._mix_place_btn.setStyleSheet(_PLACE_BTN_STYLE)
        self._mix_place_btn.setToolTip(
            "Place the whole mix: in a row unless the bar over the map says "
            "otherwise.")
        self._mix_place_btn.clicked.connect(self._on_place_mix_clicked)
        self._mix_place_btn.setEnabled(False)
        btn_row.addWidget(self._mix_place_btn)
        self._mix_clear_btn = QPushButton("Clear mix")
        self._mix_clear_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #ef9a9a; "
            "border: 1px solid #4a2e2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_clear_btn.setToolTip(
            "Empty the current mix. Plants already placed on the map stay\n"
            "where they are — use Undo (Ctrl+Z) to take those back."
        )
        self._mix_clear_btn.clicked.connect(self._clear_mix)
        self._mix_clear_btn.setEnabled(False)
        btn_row.addWidget(self._mix_clear_btn)

        self._mix_save_btn = QPushButton("Save as Community")
        self._mix_save_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #a5d6a7; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #4a7a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_save_btn.setToolTip(
            "Hex-pack the current stack into a disc and save it as a "
            "named Plant Community (appears in the Plant Community tab)."
        )
        self._mix_save_btn.clicked.connect(self._on_save_stack_as_community)
        self._mix_save_btn.setEnabled(False)
        btn_row.addWidget(self._mix_save_btn)

        self._mix_open_builder_btn = QPushButton("Open in Builder…")
        self._mix_open_builder_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #a5d6a7; "
            "border: 1px solid #2e4a2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #4a7a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
        )
        self._mix_open_builder_btn.setToolTip(
            "Pre-populate the visual builder with this stack so you can "
            "tweak positions before saving it as a Plant Community."
        )
        self._mix_open_builder_btn.clicked.connect(self._on_open_stack_in_builder)
        self._mix_open_builder_btn.setEnabled(False)
        btn_row.addWidget(self._mix_open_builder_btn)
        btn_row.addStretch()
        # Hidden while the mix is empty: four disabled buttons under a one-line
        # hint cost the list a row and offered nothing to do.
        self._mix_actions = QWidget()
        btn_row.setContentsMargins(0, 0, 0, 0)
        self._mix_actions.setLayout(btn_row)
        self._mix_actions.setVisible(False)
        ml.addWidget(self._mix_actions)

        # Its own height and no more, so the list above keeps the rest.
        mix_box.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Minimum)
        self._mix_box = mix_box
        outer.addWidget(mix_box)

    def _on_pattern_kind_changed(self, kind: str):
        # Switching Row → Grid in the bar changes how the map places, so it
        # re-arms rather than leave the map holding the old pattern. Fill Area
        # included since V2.98: choosing it in the bar starts the drawing.
        if self._armed:
            self._rearm_timer.stop()
            self._on_place_clicked()

    def _current_pattern(self) -> dict:
        """Build the pattern dict to pass to the map-placement signal.

        While the mix is what is placed and the mode is multi-cell
        (row/grid/circle), the pattern's params get a `polyculture` key
        carrying the resolved species list, distribution strategy, and
        effective spacing — App._enter_plant_mode uses this to override
        the primary's spacing on the map, and App._on_pattern_placed
        uses it to assign species across positions. Only then: until V2.99 a
        built mix rode along on any plant's Row, and the map planted the mix.
        """
        pattern = self._placement.current_pattern()
        if pattern["kind"] == "single":
            return {"kind": "single"}
        poly = self.active_polyculture() if self._armed_mix else None
        if poly is not None:
            pattern["params"]["polyculture"] = poly
        return pattern

    # ── Polyculture mix ───────────────────────────────────────────────────

    def active_polyculture(self) -> Optional[dict]:
        """Return the current mix recipe, or None if fewer than 2 species.

        Recipe shape (all fields JSON-safe so it can travel through Qt
        signals and into the project file unchanged):
            {
              "species": [{"id", "common_name", "spacing_m",
                           "plant_type", "color", "weight"}, ...],
              "strategy": "even_split",
              "spacing_strategy": "max",
              "effective_spacing_m": float,
            }

        The mix is the explicit `_mix_species` list, populated only via
        the right-click "Add to Polyculture Mix" action. Each entry
        carries `_weight` (an integer ratio set by the row's spinner,
        defaulting to 1); equal weights ⇒ exactly equal split.
        """
        if len(self._mix_species) < 2:
            return None
        species = [
            {
                "id": int(p["id"]),
                "common_name": p.get("common_name") or "",
                "spacing_m": float(p.get("spacing_meters") or 1.0),
                "plant_type": p.get("plant_type") or "herb",
                "color": p.get("marker_color") or "",
                "weight": float(p.get("_weight", 1) or 1),
            }
            for p in self._mix_species if p.get("id")
        ]
        if len(species) < 2:
            return None
        from src.polyculture import resolve_spacing
        eff = resolve_spacing(species, "max")
        return {
            "species": species,
            "strategy": "even_split",
            "spacing_strategy": "max",
            "effective_spacing_m": eff,
        }

    def peek_pending_polyculture(self) -> Optional[dict]:
        """Return the recipe stashed at Place-click time *without* clearing it.

        App calls this from `_on_pattern_placed`. We deliberately do not
        clear the stash here so the user can drop multiple identical
        polyculture patterns back-to-back without re-clicking Place
        Mix. The stash is replaced when Place Mix is clicked again
        (`_on_place_clicked`) and cleared when plant mode exits
        (`clear_pending_polyculture`).
        """
        return self._pending_polyculture

    def clear_pending_polyculture(self):
        """Drop the in-flight recipe — called when plant mode is cancelled."""
        self._pending_polyculture = None

    def _add_to_mix(self, plant: dict):
        """Add a plant to the mix, ignoring duplicates and DB-less rows.

        Stores a shallow copy so we can attach a per-mix `_weight`
        without mutating the canonical plant dict in the search
        results.
        """
        pid = plant.get("id")
        if not pid:
            return
        if any(s.get("id") == pid for s in self._mix_species):
            return
        if len(self._mix_species) >= self._MIX_MAX:
            return
        entry = dict(plant)
        entry["_weight"] = 1
        self._mix_species.append(entry)
        self._refresh_mix_list()

    def _add_to_mix_by_id(self, plant_id: int):
        """Add a plant to the mix by id — used by the drag-and-drop drop target.

        Looks the plant up in the current results first (cheap, already loaded);
        falls back to the catalogue so a drag still works after the list has
        been re-filtered."""
        try:
            pid = int(plant_id)
        except (TypeError, ValueError):
            return
        m = self._results_model
        for i in range(m.rowCount()):
            p = m.data(m.index(i), _PLANT_OBJ_ROLE)
            if p and p.get("id") == pid:
                self._add_to_mix(p)
                return
        try:
            from src.db.plants import get_plant
            p = get_plant(pid)
        except Exception:
            p = None
        if p:
            self._add_to_mix(p)

    def _remove_from_mix(self, plant_id: int):
        before = len(self._mix_species)
        self._mix_species = [
            s for s in self._mix_species if s.get("id") != plant_id
        ]
        if len(self._mix_species) != before:
            self._refresh_mix_list()

    def _clear_mix(self):
        if not self._mix_species:
            return
        self._mix_species = []
        self._refresh_mix_list()

    def _refresh_mix_list(self):
        """Rebuild the species rows + status label from `_mix_species`.

        Each row is a custom QFrame: type-icon + common name + ratio
        spinner + × remove button; four show and the rest scroll. A mix being
        placed follows its rows, and when fewer than two are left the map
        stands down rather than keep the old recipe. A plant being placed is
        not the mix, and building one beside it changes nothing on the map.
        """
        # Tear down old rows (stop signal connections from leaking).
        while self._mix_rows_layout.count():
            item = self._mix_rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        n = len(self._mix_species)
        self._mix_place_btn.setEnabled(n >= 2)
        self._mix_actions.setVisible(n > 0)
        if self._armed and self._armed_mix:
            if n >= 2:
                self._sync_fill_spacing()
                self._on_place_clicked()
            else:
                self.placement_cancelled.emit()

        if n == 0:
            self._mix_status.setText(
                "Drag or right-click plants here to build a mix."
            )
            self._mix_rows_scroll.setVisible(False)
            self._mix_rows_container.setVisible(False)
            self._mix_clear_btn.setEnabled(False)
            self._mix_save_btn.setEnabled(False)
            self._mix_open_builder_btn.setEnabled(False)
            self._refresh_page()
            return

        all_sp = [float(s.get("spacing_meters") or 1.0) for s in self._mix_species]
        eff = max(all_sp) if all_sp else 1.0
        if n == 1:
            self._mix_status.setText("1 species — add ≥1 more to activate.")
        else:
            ratios = ":".join(str(int(s.get("_weight", 1) or 1))
                              for s in self._mix_species)
            self._mix_status.setText(
                f"{n} species · {ratios} · ~{eff:.1f} m spacing"
            )
        self._mix_rows_scroll.setVisible(True)
        self._mix_rows_container.setVisible(True)
        self._mix_clear_btn.setEnabled(True)
        # Save/Open-Builder are only meaningful with ≥2 species — single
        # species "communities" are just plants.
        can_save = n >= 2
        self._mix_save_btn.setEnabled(can_save)
        self._mix_open_builder_btn.setEnabled(can_save)

        for idx, s in enumerate(self._mix_species):
            row = self._build_mix_row(idx, s)
            self._mix_rows_layout.addWidget(row)
        QTimer.singleShot(0, self._fit_mix_rows)
        self._refresh_page()

    def _fit_mix_rows(self):
        """Show every row up to four, then scroll. A scroll area asks for its
        minimum, not its content: left to itself it gave a three-plant mix
        34 px, one row of the three."""
        cap = _MIX_ROWS_VISIBLE * 26 + 8
        self._mix_rows_scroll.setFixedHeight(
            min(self._mix_rows_container.sizeHint().height() + 2, cap))

    def _sync_fill_spacing(self):
        """Start Fill Area at the plants' own spacing (V2.98): the mix's, as
        its line shows it ("~0.3 m spacing"), or the plant's. It defaulted to
        1.5 m whatever was planted, 25 times sparser than a forb mix's own
        guidance. Set when what is placed changes, so an edit to it lasts."""
        if self._armed_mix and len(self._mix_species) >= 2:
            spacing = max(float(s.get("spacing_meters") or 1.0)
                          for s in self._mix_species)
        elif self._armed_plant:
            spacing = self._armed_plant.get("spacing_meters")
        else:
            return
        self._placement.set_fill_spacing(spacing)

    def _build_mix_row(self, idx: int, species: dict) -> QFrame:
        """One species line: clickable colour dot + name + ratio spinner + ×.

        The dot is per-row clickable: it opens a QColorDialog and writes
        the chosen hex into `self._mix_species[idx]["marker_color"]` only.
        The canonical plant row (and any single-species placements that
        use the global picker) are untouched, so each polyculture mix
        can carry its own colour palette without polluting the DB.
        """
        row = QFrame()
        row.setStyleSheet(
            "QFrame { background: #1e2e1e; border: 1px solid #2e4a2e; "
            "border-radius: 3px; }"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(4)

        # Clickable colour dot — overrides the type colour for this mix only.
        dot = QPushButton()
        dot.setFixedSize(14, 14)
        dot.setCursor(Qt.CursorShape.PointingHandCursor)
        dot.setToolTip(
            "Click to set this species' marker colour for this plant community mix"
        )
        self._style_mix_dot(dot, species)
        dot.clicked.connect(
            lambda _checked=False, i=idx, btn=dot: self._on_mix_dot_clicked(i, btn)
        )
        rl.addWidget(dot)

        name = QLabel(species.get("common_name") or "—")
        name.setStyleSheet("color: #c8e6c9; font-size: 11px;")
        name.setToolTip(species.get("scientific_name") or "")
        rl.addWidget(name, 1)

        spin = QSpinBox()
        spin.setRange(1, 9)
        spin.setValue(int(species.get("_weight", 1) or 1))
        spin.setFixedWidth(46)
        spin.setToolTip(
            "Ratio: how many of this species per cycle.\n"
            "Equal numbers (default 1:1:1…) ⇒ exact even split.\n"
            "Set 2 to get twice as many of this species, etc."
        )
        spin.setStyleSheet(_QTY_SPIN_STYLE)
        # Capture idx by default-arg so each row's signal binds to its own row.
        spin.valueChanged.connect(
            lambda v, i=idx: self._on_mix_weight_changed(i, v)
        )
        rl.addWidget(spin)

        rm = QPushButton("✕")
        rm.setFixedSize(20, 20)
        rm.setToolTip("Remove from mix")
        rm.setStyleSheet(
            "QPushButton { background: transparent; color: #ef9a9a; "
            "border: 1px solid transparent; border-radius: 3px; "
            "font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; background: #2e1a1a; }"
        )
        pid = species.get("id")
        rm.clicked.connect(lambda: self._remove_from_mix(int(pid)) if pid else None)
        rl.addWidget(rm)

        return row

    @staticmethod
    def _style_mix_dot(btn: QPushButton, species: dict):
        """Repaint a mix-row dot using its per-mix marker_color override
        (falling back to the type colour). Border is a darker tint so the
        dot is clearly clickable."""
        color_hex = (species.get("marker_color")
                     or _TYPE_COLORS.get(species.get("plant_type", ""), "#78909c"))
        btn.setStyleSheet(
            f"QPushButton {{ background: {color_hex}; border: 1px solid #0d160d; "
            f"border-radius: 7px; min-width: 14px; min-height: 14px; }}"
            f"QPushButton:hover {{ border-color: #a5d6a7; }}"
        )

    def _on_mix_dot_clicked(self, idx: int, btn: QPushButton):
        if not (0 <= idx < len(self._mix_species)):
            return
        species = self._mix_species[idx]
        current = (species.get("marker_color")
                   or _TYPE_COLORS.get(species.get("plant_type", ""), "#66bb6a"))
        initial = QColor(current)
        color = QColorDialog.getColor(
            initial, self,
            f"Marker colour for {species.get('common_name', '')} (this mix)"
        )
        if not color.isValid():
            return
        species["marker_color"] = color.name()
        self._style_mix_dot(btn, species)
        self._on_pattern_params_changed()     # the armed recipe carries colours

    def _on_mix_weight_changed(self, idx: int, value: int):
        if 0 <= idx < len(self._mix_species):
            self._mix_species[idx]["_weight"] = max(1, int(value))
            # Update only the status line — rebuilding rows would
            # disturb the spinner the user is interacting with.
            self._refresh_mix_status_only()
            self._on_pattern_params_changed()  # …and the armed recipe

    def _refresh_mix_status_only(self):
        n = len(self._mix_species)
        if n < 2:
            return
        all_sp = [float(s.get("spacing_meters") or 1.0) for s in self._mix_species]
        eff = max(all_sp) if all_sp else 1.0
        ratios = ":".join(str(int(s.get("_weight", 1) or 1))
                          for s in self._mix_species)
        self._mix_status.setText(
            f"{n} species · {ratios} · ~{eff:.1f} m spacing"
        )

    # ── Save stack as Plant Community ──────────────────────────────────────

    def _stack_for_export(self) -> list[dict]:
        """Return the current mix in the shape stack_to_community_members
        expects (id, common_name, spacing_m, plant_type, color, _weight)."""
        out: list[dict] = []
        for s in self._mix_species:
            pid = s.get("id")
            if not pid:
                continue
            out.append({
                "id": int(pid),
                "common_name": s.get("common_name") or "",
                "spacing_m": float(s.get("spacing_meters") or 1.0),
                "plant_type": s.get("plant_type") or "herb",
                "color": s.get("marker_color") or "",
                "_weight": int(s.get("_weight") or 1),
            })
        return out

    def _prompt_unique_community_name(self, default: str) -> Optional[str]:
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from src.db import polycultures
        name, ok = QInputDialog.getText(
            self, "Save Plant Community",
            "Name for the new plant community:", text=default,
        )
        if not ok:
            return None
        name = name.strip()
        if not name:
            return None
        if polycultures.get_polyculture_by_name(name) is not None:
            base = name
            suffix = 2
            while polycultures.get_polyculture_by_name(f"{base} {suffix}") is not None:
                suffix += 1
            name = f"{base} {suffix}"
            QMessageBox.information(
                self, "Renamed",
                f"A community with that name already exists. "
                f"Saved as '{name}' instead."
            )
        return name

    def _on_save_stack_as_community(self):
        from PyQt6.QtWidgets import QMessageBox
        from src.db import polycultures
        from src.polyculture import stack_to_community_members
        stack = self._stack_for_export()
        if len(stack) < 2:
            return
        default = " + ".join(s["common_name"] for s in stack[:3])
        if len(stack) > 3:
            default += f" +{len(stack)-3}"
        default += " mix"
        name = self._prompt_unique_community_name(default)
        if not name:
            return
        members = stack_to_community_members(stack)
        try:
            new_id = polycultures.create_polyculture(name, "", None)
            polycultures.replace_polyculture_members(new_id, members)
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not save plant community:\n{exc}")
            return
        self.communityCreated.emit()
        QMessageBox.information(
            self, "Saved",
            f"Plant community '{name}' saved with {len(members)} "
            f"members. Find it under the Plant Community tab."
        )

    def _on_open_stack_in_builder(self):
        from PyQt6.QtWidgets import QDialog, QMessageBox
        from src.db import polycultures
        from src.polyculture import stack_to_community_members
        from src.polyculture_panel import PolycultureBuilderDialog
        stack = self._stack_for_export()
        if len(stack) < 2:
            return
        members = stack_to_community_members(stack)
        dialog = PolycultureBuilderDialog(self, polyculture_id=None)
        try:
            dialog.canvas.set_members(members)
            dialog._refresh_member_list()
        except Exception:
            pass
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data.get("name"):
            return
        try:
            new_id = polycultures.create_polyculture(
                data["name"], data.get("description", ""), None
            )
            polycultures.replace_polyculture_members(new_id, data.get("members") or [])
        except Exception as exc:
            QMessageBox.critical(self, "Error",
                                 f"Could not save plant community:\n{exc}")
            return
        self.communityCreated.emit()
        QMessageBox.information(
            self, "Saved",
            f"Plant community '{data['name']}' saved."
        )

    # ── Place on map ──────────────────────────────────────────────────────────

    def _on_place_clicked(self, _item=None):
        """Arm the map with what is being placed, the plant or the mix, in
        the bar's pattern. A mix cannot go down one plant per click, so
        Single sets it aside for the selected plant (as in V2.98), or the map
        stands down when none is selected."""
        if self._armed_mix and self._placement.kind == "single":
            self._armed_mix = False
            if not self._selected_plant:
                self._nothing_to_place()
                return
            self._armed_plant = self._selected_plant
            self._update_color_btn(self._armed_plant.get("marker_color") or "")
        pattern = self._current_pattern()
        kind = pattern.get("kind")
        # Fill Area: draw a polygon and the plant, or the mix, scatters inside
        # it (evenly distributed).
        if kind == "fill":
            members, name = self._fill_members()
            if not members:
                self._nothing_to_place()
                return
            self.fill_area_requested.emit(
                members, self._placement.fill_spacing(), name,
                bool((pattern.get("params") or {}).get("matrix")))
            self._arm_as(name)
            return
        # A mix is previewed by its own first species; the recipe decides
        # which species lands where. Until V2.98 a mix with nothing selected
        # in the list could not be placed at all.
        primary = (self._mix_species[0] if self._armed_mix
                   else self._armed_plant)
        if not primary or not primary.get("id"):
            self._nothing_to_place()
            return
        # Stash the polyculture recipe in flight so App can read it back
        # in `_on_pattern_placed` after JS finishes the 2-click gesture.
        # Cleared on consumption.
        self._pending_polyculture = (pattern.get("params") or {}).get("polyculture")
        self.place_plant_requested.emit(
            primary["id"], primary["common_name"], self._qty_spin.value(),
            pattern,
        )
        self._arm_as(primary.get("common_name", ""))

    def _arm_as(self, what: str):
        self._armed_what = what or ""
        self._armed = True
        self._announce_armed()

    def _nothing_to_place(self):
        """The pattern now asks for something this panel has not got (Single
        with only a mix, say): stand the map down rather than let it keep
        placing what the bar no longer shows."""
        if self._armed:
            self.placement_cancelled.emit()

    def _on_place_mix_clicked(self):
        """Place mix: arm the whole mix. Single places one plant, so from
        Single it switches to Row; the bar shows the change and offers the
        others."""
        if len(self._mix_species) < 2:
            return
        if self._placement.kind == "single":
            self._armed = False           # no re-arm on the way through
            self._rearm_timer.stop()
            self._placement.set_kind("row")
        self._armed_mix = True
        self._sync_fill_spacing()
        self._on_place_clicked()

    def _on_plant_context_menu(self, pos):
        """Right-click context menu for plant results list."""
        index = self._results_list.indexAt(pos)
        if not index.isValid():
            return
        plant = index.data(_PLANT_OBJ_ROLE)
        if not plant:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: #1e2e1e; color: #c8e6c9; border: 1px solid #2e4a2e; }"
            "QMenu::item:selected { background: #2e4a2e; }"
        )

        act_place = menu.addAction(f"Place {plant['common_name']} on Map")
        act_place.triggered.connect(lambda: self._quick_place(plant))

        act_place5 = menu.addAction("Place ×5 on Map")
        act_place5.triggered.connect(lambda: self._quick_place(plant, 5))

        menu.addSeparator()

        # Its page, beside the list (V3.00; this menu used to expand the card
        # painted into the row). Not while placing: the map stays clear.
        if not self._armed:
            act_about = menu.addAction(f"About {plant['common_name']}")
            act_about.triggered.connect(
                lambda: self._show_page(plant, focus=True))

        menu.addSeparator()

        # Polyculture mix — only meaningful for plants with a real id.
        already_in_mix = any(
            s.get("id") == plant.get("id") for s in self._mix_species
        )
        if already_in_mix:
            act_mix = menu.addAction("Remove from current mix")
            act_mix.triggered.connect(
                lambda: self._remove_from_mix(int(plant["id"]))
            )
        else:
            act_mix = menu.addAction("Add to current mix")
            act_mix.triggered.connect(lambda: self._add_to_mix(plant))
            if not plant.get("id"):
                act_mix.setEnabled(False)
            elif len(self._mix_species) >= self._MIX_MAX:
                act_mix.setEnabled(False)
                act_mix.setText(f"Mix full ({self._MIX_MAX} species max)")

        menu.exec(self._results_list.viewport().mapToGlobal(pos))

    def _quick_place(self, plant, qty=1):
        """Place a plant straight from the context menu: Single, ``qty`` at a
        click. Set in the bar as well, so the bar says what the map does (it
        used to go round the panel, which went on showing its own pattern)."""
        self._armed = False               # no re-arms while the bar is set up
        self._rearm_timer.stop()
        self._placement.set_kind("single")
        self._qty_spin.setValue(qty)
        self._place_plant(plant)

    def _on_color_pick(self):
        """A custom marker colour for the plant being placed: the button sits
        in the bar, beside the sentence that names it."""
        plant = self._armed_plant
        if not plant or not plant.get("id"):
            return
        current = plant.get("marker_color") or ""
        initial = QColor(current) if current else QColor(
            _TYPE_COLORS.get(plant.get("plant_type", ""), "#66bb6a")
        )
        color = QColorDialog.getColor(initial, self, "Choose marker colour")
        if not color.isValid():
            return
        hex_color = color.name()  # e.g. '#ff5722'
        # Save to DB
        try:
            from src.db.plants import update_marker_color
            update_marker_color(plant["id"], hex_color)
            plant["marker_color"] = hex_color
        except Exception:
            pass
        # Update the colour button preview
        self._update_color_btn(hex_color)
        # Signal the map to update existing markers
        self.color_changed.emit(plant["id"], hex_color)
        # …and the placement armed with the old one.
        self._on_pattern_params_changed()

    def _update_color_btn(self, hex_color: str):
        """Update the colour picker button to show the current plant's colour.

        With no custom colour set, paint a rainbow conic gradient so the
        button reads obviously as a colour picker without needing the
        caption label.
        """
        if hex_color:
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background: {hex_color}; border: 1px solid #4a7a4a; "
                f"border-radius: 13px; }}"
                f"QPushButton:hover {{ border-color: #8aca8a; }}"
                f"QPushButton:focus {{ border: 2px solid #ffe082; }}"
            )
        else:
            self._color_btn.setStyleSheet(
                "QPushButton {"
                " background: qconicalgradient(cx:0.5, cy:0.5, angle:0,"
                " stop:0 #ff5252, stop:0.17 #ffb74d, stop:0.33 #fdd835,"
                " stop:0.5 #66bb6a, stop:0.67 #29b6f6, stop:0.83 #7e57c2,"
                " stop:1 #ff5252);"
                " border: 1px solid #4a7a4a; border-radius: 13px;"
                "}"
                "QPushButton:hover { border-color: #8aca8a; }"
                "QPushButton:focus { border: 2px solid #ffe082; }"
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def set_zone(self, zone: Optional[int]):
        """Called by the main window when the hardiness zone changes.

        The dedicated zone filter UI was removed; we still track the
        current zone for any future zone-aware logic (status bar,
        suggested-plants), and we no longer touch the deleted
        `_zone_filter_btn` / `_zone_label` widgets.
        """
        self._current_zone = zone
        self._check_site()

    def on_plant_removed(self, plant_id: int):
        """Notify the panel that a plant marker was removed from the map."""
        if plant_id in self._placed_counts:
            self._placed_counts[plant_id] -= 1
            if self._placed_counts[plant_id] <= 0:
                del self._placed_counts[plant_id]
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def on_plant_placed(self, plant_id: int, common_name: str):
        """Notify the panel that a plant was placed on the map."""
        self._placed_counts[plant_id] = self._placed_counts.get(plant_id, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def on_plants_placed_batch(self, placements: list[tuple[int, str]]):
        """Notify the panel that several plants were placed at once.

        Counts are updated for every (plant_id, common_name) pair, but the
        results model and the placed-list QListWidget are only rebuilt once
        at the end. This is the difference between O(N) DB lookups + list
        clears (which blocks the Qt event loop long enough that the embedded
        Leaflet view paints a stale 0x0 frame) and one rebuild — important
        when a polyculture drops 8+ markers in one click.
        """
        if not placements:
            return
        for pid, _name in placements:
            self._placed_counts[pid] = self._placed_counts.get(pid, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def on_plants_removed_batch(self, plant_ids: list[int]):
        """Notify the panel that several plants were removed at once — decrement
        counts for all, rebuild the results model once (mirrors
        on_plants_placed_batch; avoids the per-plant rebuild that made
        multi-delete lag)."""
        if not plant_ids:
            return
        for pid in plant_ids:
            if pid in self._placed_counts:
                self._placed_counts[pid] -= 1
                if self._placed_counts[pid] <= 0:
                    del self._placed_counts[pid]
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def clear_placed(self):
        """Clear the placed-plants list (e.g. on New project)."""
        self._placed_counts.clear()
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()

    def load_placed(self, plants: list[dict]):
        """Reload placed-plants list from a loaded project."""
        self._placed_counts.clear()
        for p in plants:
            pid = p.get("plant_id", 0)
            self._placed_counts[pid] = self._placed_counts.get(pid, 0) + 1
        self._results_model.set_placed_counts(self._placed_counts)
        self.placed_counts_changed.emit()


# Minimum plant-browser height the auto-fit will leave when the Plant
# Community Mix has grown enough to want the whole splitter. Roughly the
# filter dropdowns + ~3 result rows.
_MIN_BROWSER_PX = 180


# ── Stylesheets ───────────────────────────────────────────────────────────────
# `_RESULTS_LIST_STYLE` moved to src/plant_list_view.py (Chunk 4) and is
# imported at the top of this file. The remaining stylesheets are
# specific to PlantPanel widgets and stay here.

_PLACE_BTN_STYLE = """
QPushButton {
    background: #2e7d32;
    color: #e8f5e9;
    border: none;
    border-radius: 4px;
    padding: 7px 12px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover  { background: #388e3c; }
QPushButton:pressed { background: #1b5e20; }
QPushButton:disabled { background: #2a3a2a; color: #4a6a4a; }
"""

# What the map is armed with is said by the placement bar over the map
# (src/placement_bar.py), in words from src/placement_arming.py — one place for
# both panels, so the two cannot diverge.

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

