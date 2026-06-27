"""
plant_panel.py — Right-side panel: plant browser, search, filters, detail view,
place-on-map, and placed-plants list.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QListWidget, QFrame,
    QPushButton, QSizePolicy, QScrollArea,
    QGroupBox, QSpinBox, QDoubleSpinBox,
    QColorDialog, QMenu, QListView,
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QModelIndex, QSettings, QEvent,
)
from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel

# Model, delegate, vocabulary constants, and the shared QListWidget
# stylesheet now live in src/plant_list_view.py (Chunk 4 of the
# strengthening roadmap). We re-import the bits PlantPanel still
# references so the rest of this file is unchanged.
from src.plant_list_view import (
    PlantListModel,
    PlantRowDelegate,
    _TYPE_COLORS,
    _SUN_LABELS,
    _USE_LABELS,
    _WATER_LABELS,
    _AVAILABILITY_LABELS,
    _PLANT_OBJ_ROLE,
    _PLANT_EXPANDED_ROLE,
    _RESULTS_LIST_STYLE,
    _type_icon,
)

# ── PlantPanel-only vocabulary labels ────────────────────────────────────────
_TYPE_LABELS: dict[str, str] = {
    "tree":        "Tree",
    "shrub":       "Shrub",
    "herb":        "Herb / Perennial",
    "groundcover": "Groundcover",
    "vine":        "Vine",
    "root":        "Root / Bulb",
}

_DECIDUOUS_LABELS: dict[str, str] = {
    "deciduous":  "Deciduous",
    "evergreen":  "Evergreen",
    "herbaceous": "Herbaceous (dies back)",
}

_LIFECYCLE_LABELS: dict[str, str] = {
    "perennial": "Perennial",
    "annual":    "Annual",
    "biennial":  "Biennial",
}


# ── Alberta ecoregion choices (Reference Ecosystem picker, N1) ────────────────
# Order matches the dropdown; the empty-string id is "any ecoregion" (no
# filter).  Keep the ids in sync with the comma-separated tags stored in
# plants.ab_ecoregion (see data/plants_master.json + src/db/plants.py
# heuristic tagging pass).
_AB_ECOREGION_CHOICES: list[tuple[str, str]] = [
    ("Any ecoregion",          ""),
    ("Aspen Parkland (central AB)", "aspen_parkland"),
    ("Mixedgrass Prairie (south AB)", "mixedgrass_prairie"),
    ("Fescue / Foothills (SW AB)",    "fescue_foothills"),
    ("Boreal Mixedwood (north AB)",   "boreal_mixedwood"),
    ("Riparian (streamside)",         "riparian"),
    ("Wet Meadow / Marsh",            "wet_meadow"),
    ("Subalpine / Montane (mountains)", "subalpine_montane"),
]


# NOTE: calendar constants, plant list-item roles, compact row geometry
# constants, and the `_zone_badge_text` helper moved with the model and
# delegate to src/plant_list_view.py — see Chunk 4 of the strengthening
# roadmap.


# PlantListModel and PlantRowDelegate moved to src/plant_list_view.py (Chunk 4).



# OnThisDesignPanel moved to src/on_this_design_panel.py (Chunk 4).



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


# ── Main widget ───────────────────────────────────────────────────────────────

class PlantPanel(QWidget):
    """Right-hand panel for browsing, filtering and placing plants."""

    # Place a plant (or pattern of plants). The third arg is the legacy
    # quantity spinner value (used when pattern["kind"]=="single"); the
    # fourth is the pattern descriptor — see MapWidget.set_mode docstring.
    place_plant_requested = pyqtSignal(int, str, int, dict)   # plant_id, common_name, quantity, pattern
    fill_area_requested = pyqtSignal(object, float, str, bool)  # members [(pid,weight)], spacing_m, name, matrix (F3/F22)
    color_changed = pyqtSignal(int, str)                       # plant_id, hex_color
    # Emitted when "Save as Plant Community" creates a new community from
    # the stack, so the Communities tab can refresh its library list.
    communityCreated = pyqtSignal()
    # Emitted whenever _placed_counts mutates (place / clear / load / remove)
    # so the sibling On-This-Design inner tab can refresh its Plants sub-tab.
    placed_counts_changed = pyqtSignal()

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

        # Debounce timer for local search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._run_search)

        self._build_ui()

        # Restore the user's last "Restoring toward X" ecoregion choice so
        # it survives a restart. _on_ecoregion_changed is wired in
        # _build_ui, so guard against an infinite save-during-load loop by
        # setting via index without triggering an extra save.
        self._restore_ecoregion_preference()

        self._run_search()   # populate on startup
        # Snap the splitter to its auto-fit baseline on launch so the
        # bottom pane (incl. the Place Mix on Map button) is fully
        # visible even before the user touches the Plant Community Mix.
        QTimer.singleShot(0, self._refit_bottom_pane)

    def showEvent(self, event):
        # Belt-and-suspenders: the first show may happen after __init__
        # but before the splitter has real sizes (e.g. when the Plants
        # inner tab isn't the initial selection). Retry on first show so
        # the user lands on the auto-fit layout regardless of tab order.
        super().showEvent(event)
        if not getattr(self, "_did_initial_refit", False):
            self._did_initial_refit = True
            QTimer.singleShot(0, self._refit_bottom_pane)

    _SETTINGS_ECOREGION_KEY      = "plant_panel/ab_ecoregion"
    _SETTINGS_ECOREGION_AUTO_KEY = "plant_panel/ab_ecoregion_auto"

    def _restore_ecoregion_preference(self):
        """Pre-check the ecoregion combo only when a property pin has been
        dropped (V1.86).

        By default the combo shows its "Restoring toward…" placeholder with
        nothing selected — we don't pre-filter the whole library toward a
        region the user never asked for. The one exception is the auto-detected
        ecoregion written by ``site_panel._on_ecoregion`` after a pin drop, so
        a located property still seeds a sensible reference target.

        (The user's manual multi-select is still saved to QSettings by
        ``_on_ecoregion_changed`` for the running session, but is not
        re-applied as a startup default.)"""
        autodetect = QSettings().value(
            self._SETTINGS_ECOREGION_AUTO_KEY, "", type=str
        )
        wanted = {k.strip() for k in autodetect.split(",") if k.strip()}
        if not wanted:
            return
        # Restore silently — the explicit self._run_search() in __init__ picks
        # up the checked regions, and we don't want to re-write QSettings here.
        self._ecoregion_combo.set_checked_keys(wanted)

    def _on_ecoregion_changed(self):
        # Persist the full multi-select as a comma-joined list of region keys.
        QSettings().setValue(
            self._SETTINGS_ECOREGION_KEY,
            ",".join(self._ecoregion_combo.checked_keys()),
        )
        self._run_search()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._root_layout = root

        # Browser (top, stretches to fill) + placement controls (bottom,
        # collapses to just its header). A plain layout — NOT a QSplitter —
        # because QSplitter ignores a collapsed child's maximum height and
        # leaves an empty gap above the header; a QVBoxLayout honours the
        # CollapsiblePanel's collapsed sizeHint so the browser fills the space.
        # Both panes are added to `root` once built (see below).

        # ── Top pane: header + search + filters + results list ────────────
        local_tab = QWidget()
        top_layout = QVBoxLayout(local_tab)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(4)

        # Page header (V1.86) — a plain, non-collapsible title that mirrors the
        # Plant Community Library page. The old collapsible "Plant Browser"
        # header hid nothing useful when collapsed, so it's gone.
        title_label = QLabel(
            "<b>Plant Library</b>  "
            "<span style='color:#90a4ae;font-weight:normal;'>(browse &amp; place)</span>"
        )
        title_label.setStyleSheet("font-size: 13px;")
        top_layout.addWidget(title_label)

        # Search box
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search plants…")
        self._search_box.setClearButtonEnabled(True)
        self._search_box.textChanged.connect(self._on_search_changed)
        top_layout.addWidget(self._search_box)

        # ── Filter dropdowns (multi-select facets, V1.85) ─────────────────
        # Type / Sun / Water / Use / Availability are all multi-select so the
        # user can combine values within a facet (e.g. Tree + Shrub, or Full
        # Sun + Partial Shade). They share one dark-green style that blends the
        # plain combo shape with the toggle-button palette below.
        _combo_style = (
            "QComboBox { background: #1e2e1e; color: #a5d6a7; border: 1px solid #2e4a2e; "
            "border-radius: 3px; padding: 2px 6px; font-size: 11px; }"
            "QComboBox:hover { border-color: #4a7a4a; }"
            "QComboBox::drop-down { border: none; width: 16px; }"
            "QComboBox QLineEdit { background: transparent; color: #a5d6a7; border: none; }"
            "QComboBox QAbstractItemView { background: #1e2e1e; color: #cfd8dc; "
            "border: 1px solid #2e4a2e; outline: none; "
            "selection-background-color: #2e5a2e; selection-color: #a5d6a7; }"
        )
        _toggle_style = (
            "QPushButton { background: #1e2e1e; color: #78909c; border: 1px solid #2e4a2e; "
            "border-radius: 3px; padding: 2px 6px; font-size: 11px; }"
            "QPushButton:checked { background: #2e5a2e; color: #a5d6a7; border-color: #66bb6a; }"
            "QPushButton:hover { border-color: #4a7a4a; }"
        )

        # Row 1: Type + Sun. The Type items carry the plant-type colour swatch
        # (same colours as the map markers / list dots), so the dropdown doubles
        # as the legend for the coloured circles. Equal stretch keeps the two
        # columns 50/50 at any width.
        row1 = QHBoxLayout()
        row1.setSpacing(4)
        self._type_combo = self._make_multi_combo(
            "Any type", _TYPE_LABELS, _combo_style, icon_for=_type_icon)
        self._sun_combo = self._make_multi_combo("Any sun", _SUN_LABELS, _combo_style)
        row1.addWidget(self._type_combo, 1)
        row1.addWidget(self._sun_combo, 1)
        top_layout.addLayout(row1)

        # Row 2: Water + Use
        row2 = QHBoxLayout()
        row2.setSpacing(4)
        self._water_combo = self._make_multi_combo("Any water", _WATER_LABELS, _combo_style)
        self._use_combo = self._make_multi_combo("Any use", _USE_LABELS, _combo_style)
        self._use_combo.setToolTip(
            "Pick one or more uses; only plants that have ALL of them are shown."
        )
        row2.addWidget(self._water_combo, 1)
        row2.addWidget(self._use_combo, 1)
        top_layout.addLayout(row2)

        # Row 3: Availability (where to buy) + Reference ecosystem (N1), paired
        # side-by-side with the other dropdowns (V1.85). Both multi-select:
        #  * Availability — show several sourcing tiers at once (e.g. big-box +
        #    garden-centre + native-nursery) and skip the seed-only / rare tail.
        #  * Restoring toward — plants documented from ANY of the chosen Alberta
        #    ecoregions. The choice is persisted across sessions via QSettings.
        row3 = QHBoxLayout()
        row3.setSpacing(4)
        self._rarity_combo = self._make_multi_combo(
            "Any availability", _AVAILABILITY_LABELS, _combo_style)
        self._rarity_combo.setToolTip(
            "Show only plants you can source from the checked tiers.\n"
            "Leave all unchecked to see everything."
        )
        # Ecoregion choices are (label, key) tuples with a leading "Any" sentinel
        # (empty key); the multi-select combo uses its placeholder for "any", so
        # drop the sentinel and feed the real regions in display order.
        _eco_labels = {key: lbl for lbl, key in _AB_ECOREGION_CHOICES if key}
        self._ecoregion_combo = CheckableComboBox(placeholder="Restoring toward…")
        for key, lbl in _eco_labels.items():
            self._ecoregion_combo.add_check_item(lbl, key)
        self._ecoregion_combo.setStyleSheet(_combo_style)
        self._ecoregion_combo.setToolTip(
            "Restore toward one or more Alberta ecoregions — shows plants\n"
            "documented from any of them. Leave unchecked to see everything."
        )
        self._ecoregion_combo.selectionChanged.connect(self._on_ecoregion_changed)
        row3.addWidget(self._rarity_combo, 1)
        row3.addWidget(self._ecoregion_combo, 1)
        top_layout.addLayout(row3)

        # ── Toggle filters (non-dropdown extras only, V1.85) ─────────────
        # The use-based toggles (Medicinal / N-Fixer / Pollinator / Keystone /
        # Host Plant / Bird Food) moved into the multi-select Use dropdown
        # above; only the filters with no dropdown equivalent remain here.
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(3)

        self._native_filter_btn = QPushButton("Native AB")
        self._native_filter_btn.setCheckable(True)
        self._native_filter_btn.setToolTip("Only show plants native to Alberta")
        self._native_filter_btn.setStyleSheet(_toggle_style)
        self._native_filter_btn.toggled.connect(self._run_search)
        toggle_row.addWidget(self._native_filter_btn)

        self._edible_btn = QPushButton("Edible")
        self._edible_btn.setCheckable(True)
        self._edible_btn.setToolTip("Only show plants with edible parts")
        self._edible_btn.setStyleSheet(_toggle_style)
        self._edible_btn.toggled.connect(self._run_search)
        toggle_row.addWidget(self._edible_btn)

        self._perennial_btn = QPushButton("Perennial")
        self._perennial_btn.setCheckable(True)
        self._perennial_btn.setToolTip("Only show perennial plants")
        self._perennial_btn.setStyleSheet(_toggle_style)
        self._perennial_btn.toggled.connect(self._run_search)
        toggle_row.addWidget(self._perennial_btn)

        self._has_image_btn = QPushButton("Photo")
        self._has_image_btn.setCheckable(True)
        self._has_image_btn.setToolTip(
            "Only show plants that have a photo (openly licensed, from iNaturalist)"
        )
        self._has_image_btn.setStyleSheet(_toggle_style)
        self._has_image_btn.toggled.connect(self._run_search)
        toggle_row.addWidget(self._has_image_btn)

        # Result count rides at the end of the toggle row (right-aligned) to
        # save a vertical line (V1.86).
        toggle_row.addStretch(1)
        self._result_count = QLabel("Results: —")
        self._result_count.setStyleSheet("color: #78909c; font-size: 11px;")
        toggle_row.addWidget(self._result_count)
        top_layout.addLayout(toggle_row)

        # ── Compact results list (QListView + custom delegate) ─────────
        # Built on PlantListModel + PlantRowDelegate so each plant lives on
        # one ~26 px row by default (10+ visible at default panel size). The
        # chevron at the right edge expands a row inline to reveal the full
        # detail block; multiple rows can be expanded at once.
        self._results_model    = PlantListModel(self)
        self._results_list     = QListView()
        self._results_delegate = PlantRowDelegate(self._results_list)
        self._results_list.setModel(self._results_model)
        self._results_list.setItemDelegate(self._results_delegate)
        self._results_list.setSelectionMode(
            self._results_list.SelectionMode.SingleSelection
        )
        self._results_list.setUniformItemSizes(False)
        self._results_list.setStyleSheet(_RESULTS_LIST_STYLE)
        self._results_list.setVerticalScrollMode(
            self._results_list.ScrollMode.ScrollPerPixel
        )
        self._results_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_list.selectionModel().currentChanged.connect(
            self._on_view_current_changed
        )
        self._results_list.doubleClicked.connect(self._on_view_double_clicked)
        self._results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._results_list.customContextMenuRequested.connect(self._on_plant_context_menu)
        top_layout.addWidget(self._results_list)

        # The browser pane is no longer collapsible (V1.86): collapsing it
        # revealed nothing useful and only confused users. The "Plant Library"
        # header sits inline at the top of the pane (added above).
        root.addWidget(local_tab, 1)   # stretches to fill the sidebar

        # ── Bottom: placement controls + placed plants ────────────────────
        bottom = QWidget()
        bot_layout = QVBoxLayout(bottom)
        bot_layout.setContentsMargins(8, 4, 8, 8)
        bot_layout.setSpacing(6)

        # The legacy "Selected Plant" detail group + standalone planting
        # calendar QGroupBox were removed — both are now redundant with
        # the inline-expand chevron in the results list (which shows the
        # full detail block + the 12-cell colour-coded month strip in
        # one place).

        # ── Pattern mode selector ───────────────────────────────────────
        # Single = click-to-place (current behaviour). Row/Grid/Circle take
        # two clicks each and emit a single batch placement with shared
        # group_id. The placement-controls widget is shared with the Plant
        # Communities tab so both tabs expose identical placement options.
        from src.placement_controls import PlacementControlsWidget
        self._placement = PlacementControlsWidget(show_canopy_base=True)
        self._placement.patternKindChanged.connect(self._on_pattern_kind_changed)
        bot_layout.addWidget(self._placement)
        self._build_polyculture_controls(bot_layout)

        # ── Placement controls: quantity + colour + place button ───────
        place_row = QHBoxLayout()
        place_row.setSpacing(4)

        # Quantity spinner — only meaningful for Single mode (burst placement).
        qty_label = QLabel("Qty:")
        qty_label.setStyleSheet("color: #90a4ae; font-size: 11px;")
        self._qty_spin = QSpinBox()
        self._qty_spin.setMinimum(1)
        self._qty_spin.setMaximum(50)
        self._qty_spin.setValue(1)
        self._qty_spin.setFixedWidth(65)
        self._qty_spin.setToolTip("Single mode: how many plants to burst at the click point\n"
                                  "Ignored in Row/Grid/Circle modes")
        self._qty_spin.setStyleSheet(_QTY_SPIN_STYLE)
        place_row.addWidget(qty_label)
        place_row.addWidget(self._qty_spin)

        # Colour picker — small caption "Colour" sits directly above a
        # rainbow-tinted circular button so the affordance is obvious
        # both by label and by icon.
        color_col = QVBoxLayout()
        color_col.setContentsMargins(0, 0, 0, 0)
        color_col.setSpacing(2)
        color_caption = QLabel("Colour")
        color_caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        color_caption.setStyleSheet("color: #90a4ae; font-size: 10px;")
        color_col.addWidget(color_caption)

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(28, 28)
        self._color_btn.setToolTip(
            "Set a custom marker colour for this plant.\n"
            "Click to open the colour picker."
        )
        self._color_btn.clicked.connect(self._on_color_pick)
        color_col.addWidget(self._color_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        place_row.addLayout(color_col)
        # Show the rainbow default until a plant is selected with a custom colour.
        self._update_color_btn("")

        # Place on Map button
        self._place_btn = QPushButton("Place on Map")
        self._place_btn.setEnabled(False)
        self._place_btn.setToolTip("Click to enter plant-placement mode on the map")
        self._place_btn.clicked.connect(self._on_place_clicked)
        self._place_btn.setStyleSheet(_PLACE_BTN_STYLE)
        place_row.addWidget(self._place_btn)

        bot_layout.addLayout(place_row)
        # Fill Area now lives in the Placement Mode selector (choose "Fill Area",
        # set spacing, click Place, then draw the polygon) — see
        # _on_place_clicked + PlacementControlsWidget.

        # Bottom pane: just placement controls now. (On This Design lives
        # in a sibling inner tab at the same level as Plants and Plant
        # Communities — see app.py's inner QTabWidget.) The widget+scroll
        # area pair is kept as instance attrs so `_refit_bottom_pane` can
        # auto-size the splitter when the mix grows/shrinks.
        self._bottom_widget = bottom
        bottom.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self._bottom_scroll = QScrollArea()
        self._bottom_scroll.setWidget(bottom)
        self._bottom_scroll.setWidgetResizable(True)
        self._bottom_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._bottom_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._bottom_scroll.setMinimumHeight(140)
        # Cap the expanded height so a big plant-mix scrolls inside the pane
        # rather than pushing the browser off-screen.
        self._bottom_scroll.setMaximumHeight(360)

        # Wrap the placement pane in a CollapsiblePanel so it can shrink to just
        # a header, freeing the whole sidebar for the results list when the user
        # isn't placing. (Placement collapsing IS useful — unlike the old
        # browser-pane collapse — so it stays.) Minimised by default so the tab
        # opens with the results list filling the sidebar.
        from src.collapsible_panel import CollapsiblePanel
        self._placement_panel = CollapsiblePanel(
            "Placement", panel_id="plant_panel_placement", expanded=False
        )
        self._placement_panel.set_content(self._bottom_scroll)

        # stretch 0: the placement panel takes its content height when expanded
        # and collapses to a bare header at the bottom; the browser above keeps
        # the rest of the column.
        root.addWidget(self._placement_panel)

    # ── Filter helpers ────────────────────────────────────────────────────────

    def _make_multi_combo(self, placeholder: str, labels: dict,
                          style: str, icon_for=None) -> "CheckableComboBox":
        """Build a styled multi-select facet dropdown (V1.85).

        ``labels`` is a key→label dict; selecting items re-runs the search.
        ``icon_for(key)`` (optional) returns a per-item QIcon — used to put the
        plant-type colour swatch beside each Type, doubling as the map legend.
        """
        combo = CheckableComboBox(placeholder=placeholder)
        for key, lbl in labels.items():
            combo.add_check_item(lbl, key,
                                 icon=icon_for(key) if icon_for else None)
        combo.setStyleSheet(style)
        combo.selectionChanged.connect(self._run_search)
        return combo

    # ── Search / filter ───────────────────────────────────────────────────────

    def _on_search_changed(self, _text: str):
        self._search_timer.start()

    def set_soil_ph(self, ph):
        """Set the site's soil pH (from site data) so the browser only shows
        plants tolerant of it. ``None`` clears the constraint. Re-runs the
        search so results reflect the change immediately (V1.67)."""
        new = float(ph) if isinstance(ph, (int, float)) else None
        if new == self._soil_ph:
            return
        self._soil_ph = new
        self._run_search()

    def _run_search(self):
        try:
            from src.db.plants import search_plants
        except Exception:
            return

        # The dedicated zone-filter toggle was removed; results are
        # never zone-restricted now. `_current_zone` is still tracked
        # for status-bar display elsewhere.
        zone = None

        # Facet dropdowns are multi-select (V1.85): each returns a list of
        # checked keys. The use-based toggles moved into the Use dropdown; only
        # the column-based toggles (Native AB / Edible / Perennial / Photo)
        # remain as buttons.
        try:
            plants = search_plants(
                query       = self._search_box.text().strip(),
                plant_type  = self._type_combo.checked_keys(),
                sun_req     = self._sun_combo.checked_keys(),
                water_needs = self._water_combo.checked_keys(),
                perm_use    = self._use_combo.checked_keys(),
                zone        = zone,
                native_only = self._native_filter_btn.isChecked(),
                edible_only = self._edible_btn.isChecked(),
                perennial_only = self._perennial_btn.isChecked(),
                has_image_only  = self._has_image_btn.isChecked(),
                ab_ecoregion    = self._ecoregion_combo.checked_keys(),
                availability_in = self._rarity_combo.checked_keys(),
                soil_ph         = self._soil_ph,
            )
        except Exception as exc:
            self._result_count.setText(f"Error: {exc}")
            return

        self._results_model.set_plants(plants)
        self._results_model.set_placed_counts(self._placed_counts)

        n = len(plants)
        self._result_count.setText(f"Results: {n}")

    # ── Selection / detail ────────────────────────────────────────────────────

    def _on_view_current_changed(self, current: QModelIndex, _prev: QModelIndex):
        """QListView equivalent of the old QListWidget currentItemChanged.

        Selecting a row enables the Place button and updates the colour-
        picker preview. The compact-list flow doesn't surface a separate
        bottom detail group — the inline expand chevron is the discovery
        path.
        """
        if not current.isValid():
            self._selected_plant = None
            self._place_btn.setEnabled(False)
            return
        plant = current.data(_PLANT_OBJ_ROLE)
        if not plant:
            self._selected_plant = None
            # A built mix can still be Placed (incl. Fill Area) without a
            # current list selection.
            self._place_btn.setEnabled(len(self._mix_species) >= 2)
            return
        self._selected_plant = plant
        self._update_color_btn(plant.get("marker_color") or "")
        self._place_btn.setEnabled(True)

    def _on_view_double_clicked(self, index: QModelIndex):
        """Double-click: place the plant directly (Single mode)."""
        if not index.isValid():
            return
        plant = index.data(_PLANT_OBJ_ROLE)
        if plant:
            self._selected_plant = plant
            self._on_place_clicked()

    # ── Fill an area with plants (Placement Mode → Fill Area) ───────────────────

    def _fill_members(self):
        """``(members, name)`` for an area fill: the current mix (≥2 species) if
        one is built, else the selected single plant. ``members`` is a list of
        ``(plant_id, weight)``."""
        if len(self._mix_species) >= 2:
            members = [(int(s["id"]), float(s.get("_weight", 1) or 1))
                       for s in self._mix_species if s.get("id")]
            return members, "Custom mix"
        if self._selected_plant and self._selected_plant.get("id"):
            return ([(int(self._selected_plant["id"]), 1.0)],
                    self._selected_plant.get("common_name", ""))
        return [], ""

    # ── Place on map ──────────────────────────────────────────────────────────

    # ── Pattern mode UI ───────────────────────────────────────────────────────

    def _build_polyculture_controls(self, outer: QVBoxLayout):
        """Build the inline stack-mix UI inside the placement group."""
        mix_box = QGroupBox("Plant current mix")
        mix_box.setStyleSheet(
            "QGroupBox { color: #a5d6a7; font-size: 11px; "
            "border: 1px solid #2e4a2e; border-radius: 4px; margin-top: 8px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 8px; "
            "padding: 0 4px; }"
        )
        ml = QVBoxLayout(mix_box)
        ml.setContentsMargins(6, 6, 6, 6)
        ml.setSpacing(3)

        self._mix_status = QLabel(
            "Mix off — right-click a plant in the list to add it.\n"
            "With ≥2 species, Row/Grid/Circle will mix them across the placement."
        )
        self._mix_status.setWordWrap(True)
        self._mix_status.setStyleSheet("color: #78909c; font-size: 10px;")
        ml.addWidget(self._mix_status)

        # ── Species rows (one per mix entry, custom widgets) ─────────
        self._mix_rows_container = QWidget()
        self._mix_rows_layout = QVBoxLayout(self._mix_rows_container)
        self._mix_rows_layout.setContentsMargins(0, 2, 0, 2)
        self._mix_rows_layout.setSpacing(2)
        self._mix_rows_container.setVisible(False)
        ml.addWidget(self._mix_rows_container)

        # ── Action buttons (clear, save as community) ────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        self._mix_clear_btn = QPushButton("Clear mix")
        self._mix_clear_btn.setStyleSheet(
            "QPushButton { background: #1e2e1e; color: #ef9a9a; "
            "border: 1px solid #4a2e2e; border-radius: 3px; "
            "padding: 2px 8px; font-size: 11px; }"
            "QPushButton:hover { border-color: #8a4a4a; }"
            "QPushButton:disabled { color: #455a64; border-color: #2e4a2e; }"
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
        ml.addLayout(btn_row)

        outer.addWidget(mix_box)

    def _on_pattern_kind_changed(self, kind: str):
        # Burst quantity only applies in Single mode.
        self._qty_spin.setEnabled(kind == "single")

    def _current_pattern(self) -> dict:
        """Build the pattern dict to pass to the map-placement signal.

        When a stack mix is active and the mode is multi-cell
        (row/grid/circle), the pattern's params get a `polyculture` key
        carrying the resolved species list, distribution strategy, and
        effective spacing — App._enter_plant_mode uses this to override
        the primary's spacing on the map, and App._on_pattern_placed
        uses it to assign species across positions.
        """
        pattern = self._placement.current_pattern()
        if pattern["kind"] == "single":
            return {"kind": "single"}
        poly = self.active_polyculture()
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
        spinner + × remove button. The whole stack is always visible
        (no scroll) so all ≤8 species fit at once. Also updates the
        Place button's text and the recipe combo's "active" tooltip
        so users see at a glance that a polyculture is queued up.
        """
        # Tear down old rows (stop signal connections from leaking).
        while self._mix_rows_layout.count():
            item = self._mix_rows_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        n = len(self._mix_species)

        # Place button label tracks the active mix; a built mix is placeable
        # (incl. Fill Area) even when nothing is selected in the list.
        if hasattr(self, "_place_btn"):
            self._place_btn.setText(
                "Place Mix on Map" if n >= 2 else "Place on Map"
            )
            if n >= 2:
                self._place_btn.setEnabled(True)

        if n == 0:
            self._mix_status.setText(
                "Mix off — right-click a plant in the list to add it.\n"
                "With ≥2 species, Row/Grid/Circle will mix them in equal "
                "ratios (adjust per-row to skew)."
            )
            self._mix_rows_container.setVisible(False)
            self._mix_clear_btn.setEnabled(False)
            self._mix_save_btn.setEnabled(False)
            self._mix_open_builder_btn.setEnabled(False)
            QTimer.singleShot(0, self._refit_bottom_pane)
            return

        all_sp = [float(s.get("spacing_meters") or 1.0) for s in self._mix_species]
        eff = max(all_sp) if all_sp else 1.0
        if n == 1:
            self._mix_status.setText(
                f"Mix: 1 species (need ≥2 to activate).\n"
                f"Add at least one more, then choose Row/Grid/Circle."
            )
        else:
            ratios = ":".join(str(int(s.get("_weight", 1) or 1))
                              for s in self._mix_species)
            self._mix_status.setText(
                f"Plant community: {n} species at {ratios} — spacing "
                f"{eff:.2f} m (max). Click Place Mix on Map."
            )
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
        # Auto-fit the bottom pane: grow it (eating into the plant browser)
        # so all the freshly added mix rows are visible without scrolling.
        # Deferred to the next event-loop tick so the new rows have been
        # laid out and contribute to sizeHint().
        QTimer.singleShot(0, self._refit_bottom_pane)

    def _refit_bottom_pane(self):
        """No-op since V1.79: the placement pane is no longer in a QSplitter, so
        there is nothing to resize. The CollapsiblePanel sizes itself to its
        content when expanded (capped by `_bottom_scroll`'s max height) and to a
        bare header when collapsed, with the browser above taking the rest.
        Kept (rather than deleted) so existing call sites stay harmless."""
        return

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

    def _on_mix_weight_changed(self, idx: int, value: int):
        if 0 <= idx < len(self._mix_species):
            self._mix_species[idx]["_weight"] = max(1, int(value))
            # Update only the status line — rebuilding rows would
            # disturb the spinner the user is interacting with.
            self._refresh_mix_status_only()

    def _refresh_mix_status_only(self):
        n = len(self._mix_species)
        if n < 2:
            return
        all_sp = [float(s.get("spacing_meters") or 1.0) for s in self._mix_species]
        eff = max(all_sp) if all_sp else 1.0
        ratios = ":".join(str(int(s.get("_weight", 1) or 1))
                          for s in self._mix_species)
        self._mix_status.setText(
            f"Plant community: {n} species at {ratios} — spacing "
            f"{eff:.2f} m (max). Click Place Mix on Map."
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
        pattern = self._current_pattern()
        # Fill Area is a placement mode now: draw a polygon and the selected
        # plant — or the current mix — scatters inside it (evenly distributed).
        if pattern.get("kind") == "fill":
            members, name = self._fill_members()
            if not members:
                return
            self.fill_area_requested.emit(
                members, self._placement.fill_spacing(), name,
                bool((pattern.get("params") or {}).get("matrix")))
            return
        if not self._selected_plant:
            return
        # Stash the polyculture recipe in flight so App can read it back
        # in `_on_pattern_placed` after JS finishes the 2-click gesture.
        # Cleared on consumption.
        self._pending_polyculture = (
            (pattern.get("params") or {}).get("polyculture")
            if isinstance(pattern, dict) else None
        )
        self.place_plant_requested.emit(
            self._selected_plant["id"],
            self._selected_plant["common_name"],
            self._qty_spin.value(),
            pattern,
        )

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

        expanded = bool(index.data(_PLANT_EXPANDED_ROLE))
        act_expand = menu.addAction("Collapse details" if expanded else "Expand details")
        act_expand.triggered.connect(
            lambda: self._results_model.toggle_expanded(index.row())
        )

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
        """Place a plant directly from context menu (always Single mode)."""
        self.place_plant_requested.emit(
            plant["id"], plant["common_name"], qty, {"kind": "single"}
        )

    def _on_color_pick(self):
        """Open a colour picker to set a custom marker colour for the selected plant."""
        if not self._selected_plant or not self._selected_plant.get("id"):
            return
        plant = self._selected_plant
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
            self._selected_plant["marker_color"] = hex_color
        except Exception:
            pass
        # Update the colour button preview
        self._update_color_btn(hex_color)
        # Signal the map to update existing markers
        self.color_changed.emit(plant["id"], hex_color)

    def _update_color_btn(self, hex_color: str):
        """Update the colour picker button to show the current plant's colour.

        With no custom colour set, paint a rainbow conic gradient so the
        button reads obviously as a colour picker without needing the
        caption label.
        """
        if hex_color:
            self._color_btn.setStyleSheet(
                f"QPushButton {{ background: {hex_color}; border: 1px solid #4a7a4a; "
                f"border-radius: 14px; }}"
                f"QPushButton:hover {{ border-color: #8aca8a; }}"
            )
        else:
            self._color_btn.setStyleSheet(
                "QPushButton {"
                " background: qconicalgradient(cx:0.5, cy:0.5, angle:0,"
                " stop:0 #ff5252, stop:0.17 #ffb74d, stop:0.33 #fdd835,"
                " stop:0.5 #66bb6a, stop:0.67 #29b6f6, stop:0.83 #7e57c2,"
                " stop:1 #ff5252);"
                " border: 1px solid #4a7a4a; border-radius: 14px;"
                "}"
                "QPushButton:hover { border-color: #8aca8a; }"
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

