"""
app.py — Main application window for PermaDesign.

Layout
------
  ┌─────────────────────────────────────────┐
  │  Menu bar                               │
  │  Toolbar                                │
  ├──────────────────────┬──────────────────┤
  │                      │                  │
  │   MapWidget  (70%)   │  PlantPanel(30%) │
  │                      │                  │
  ├──────────────────────┴──────────────────┤
  │  Status bar  (coords · zone · mode)     │
  └─────────────────────────────────────────┘
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QStatusBar, QLabel, QMessageBox, QFileDialog, QSizePolicy,
    QInputDialog, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer, QThread, QEvent
from PyQt6.QtGui import QKeySequence, QShortcut

from src.map_widget       import MapWidget
from src.plant_panel        import PlantPanel
from src.on_this_design_panel import OnThisDesignPanel
from src.polyculture_panel      import PolyculturePanel
from src.structure_panel  import StructurePanel
from src.analysis_panel   import AnalysisPanel
from src.planning_panel   import PlanningPanel
from src.site_panel       import SitePanel
from src.toolbar          import MainToolbar
from src.climate          import get_zone, zone_label
from src.collapsible_panel import CollapsibleSidebar
import src.project as project_io
from src.controllers.update_flow import UpdateFlowController
from src.controllers.mode import ModeController
from src.controllers.persistence import PersistenceController
from src.controllers.map_events import MapEventRouter
from src.controllers.generation import GenerationController


# Marker colour tables for plant-community members.
#
# Vegetation layer is the primary signal — when a member has a layer set
# we colour by that so the canopy structure reads at a glance on the
# map. Function colours are used only when a member has no layer (i.e.
# functional-only roles like "windbreak" or "nitrogen_fixer"). Legacy
# single-value `role` data falls through to either table.
_LAYER_COLORS = {
    'overstory':           '#1b5e20',
    'understory':          '#388e3c',
    'shrub_layer':         '#4a8b3a',
    'groundcover':         '#66bb6a',
    'herbaceous':          '#9ccc65',
    'vine':                '#7cb342',
    'root':                '#8d6e63',
}

_FUNCTION_COLORS = {
    'nitrogen_fixer':      '#43a047',
    'soil_builder':        '#2e7d32',
    'pest_deterrent':      '#7cb342',
    'pollinator':          '#aed581',
    'windbreak':           '#558b2f',
}

# Legacy aliases mapped through to the new tables so projects saved
# before the role rename still render.
_LEGACY_ROLE_ALIASES = {
    'canopy':              ('overstory',      'layer'),
    'dynamic_accumulator': ('soil_builder',   'function'),
    'pest_repellent':      ('pest_deterrent', 'function'),
}

_OTHER_COLOR = '#81c784'


def _member_color(member: dict) -> str:
    """Pick a marker colour for a polyculture member.

    Resolution order:
      1. Explicit `layer` → _LAYER_COLORS.
      2. First entry in `functions` → _FUNCTION_COLORS.
      3. Legacy single `role` (with alias mapping) → either table.
      4. Fallback to _OTHER_COLOR.
    """
    layer = (member.get('layer') or '').strip().lower()
    if layer in _LAYER_COLORS:
        return _LAYER_COLORS[layer]
    funcs = member.get('functions') or []
    if isinstance(funcs, list) and funcs:
        f0 = str(funcs[0]).strip().lower()
        if f0 in _FUNCTION_COLORS:
            return _FUNCTION_COLORS[f0]
    role = (member.get('role') or '').strip().lower()
    if role in _LEGACY_ROLE_ALIASES:
        canonical, kind = _LEGACY_ROLE_ALIASES[role]
        if kind == 'layer':
            return _LAYER_COLORS.get(canonical, _OTHER_COLOR)
        return _FUNCTION_COLORS.get(canonical, _OTHER_COLOR)
    if role in _LAYER_COLORS:
        return _LAYER_COLORS[role]
    if role in _FUNCTION_COLORS:
        return _FUNCTION_COLORS[role]
    return _OTHER_COLOR


# Back-compat shim — older code paths still reference _ROLE_COLORS by
# name. Kept as a flat lookup that covers the union of layer + function
# colours plus the legacy aliases.
_ROLE_COLORS = {
    **_LAYER_COLORS,
    **_FUNCTION_COLORS,
    'canopy':              _LAYER_COLORS['overstory'],
    'dynamic_accumulator': _FUNCTION_COLORS['soil_builder'],
    'pest_repellent':      _FUNCTION_COLORS['pest_deterrent'],
    'other':               _OTHER_COLOR,
}


def _init_database():
    """Bootstrap the plant database; show a warning on failure (don't crash)."""
    try:
        from src.db.plants import init_db
        init_db()
    except Exception as exc:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(
            None, "Database Warning",
            f"Could not initialise the plant database:\n{exc}\n\n"
            "The plant panel will be empty. "
            "Try running:  python -m src.db.seed_data"
        )


class MainWindow(QMainWindow):

    AUTOSAVE_INTERVAL_MS = 5 * 60 * 1000   # 5 minutes

    def __init__(self):
        super().__init__()
        _init_database()
        self.setWindowTitle("PermaDesign — Native Habitat Designer")
        self.resize(1400, 860)
        self.setMinimumSize(900, 600)

        # Project state
        self._project      = project_io.new_project()
        self._project_path = None        # path when saved to file
        self._modified     = False
        self._current_zone = None
        self._current_mode = 'none'

        # Placed plants list: [{plant_id, common_name, lat, lng}, ...]
        self._placed_plants = []

        # Undo/redo stacks
        self._undo_stack: list[dict] = []   # each entry: {action, data}
        self._redo_stack: list[dict] = []
        self._max_undo = 50

        # Pending anchor-mode configs (set when entering anchor mode, cleared after render)
        self._pending_sun_config:    dict | None = None
        self._pending_sun_anchor:    tuple | None = None
        self._pending_sector_config: dict | None = None
        # Community-pattern stash: when set, _on_pattern_placed expands
        # each anchor position into one full community (instead of one
        # plant). Set by _enter_polyculture_pattern_mode, cleared on
        # mode exit.
        self._pending_community_pattern: dict | None = None
        # Same idea for the community-mix case (Communities tab's ratio
        # mix of multiple plant communities).
        self._pending_community_pattern_mix: list[dict] | None = None

        # Edmonton offline download thread/worker (None when idle)
        self._dl_thread: Optional[QThread] = None
        self._dl_worker = None

        # Per-concern controllers (Chunk 5 of the strengthening roadmap).
        # Constructed before _build_ui so QAction.connect() calls in the
        # menu builder can target the controller-backed shims below.
        self._update_flow = UpdateFlowController(self)
        self._mode = ModeController(self)
        self._persistence = PersistenceController(self)
        self._map_events = MapEventRouter(self)
        self._generation = GenerationController(self)

        self._build_ui()
        self._connect_signals()
        self._start_autosave()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar — Draw row on top, Layers row stacked below it.
        # NOTE: the toolbars used to be attached to QMainWindow's toolbar
        # area (above the central widget). They now live inside the left
        # column of the central splitter so the right-hand side panel can
        # extend full-height from just below the menu bar to the status
        # bar — see _build_central_layout below.
        self.toolbar = MainToolbar(self)

        # Central area
        self.map_widget      = MapWidget(self)
        self.site_panel      = SitePanel(self)
        # Wire so the address finder can bias its Nominatim query
        # against the map's current view centre.
        self.site_panel.attach_map_widget(self.map_widget)
        self.plant_panel     = PlantPanel(self)
        self.polyculture_panel     = PolyculturePanel(self)
        # Third sibling inner tab — displays Plants / Communities / Stats
        # for the current design. Driven by _sync_planning_panel + a
        # placed_counts_changed signal from PlantPanel.
        self.on_this_design = OnThisDesignPanel()
        self.structure_panel = StructurePanel(self)
        self.analysis_panel  = AnalysisPanel(self)
        self.planning_panel  = PlanningPanel(self)

        # Tabbed side panel — five top-level tabs (Site, Plants, Structures,
        # Analysis, Planning). The Polyculture library lives under an inner
        # tab inside "Plants".
        self._plant_poly_tab = self._build_plants_polycultures_tab()

        self._side_tabs = QTabWidget()
        self._side_tabs.setDocumentMode(False)
        self._side_tabs.addTab(self.site_panel, "Site")
        self._side_tabs.addTab(self._plant_poly_tab, "Plants")
        self._side_tabs.addTab(self.structure_panel, "Structures")
        self._side_tabs.addTab(self.analysis_panel, "Analysis")
        self._side_tabs.addTab(self.planning_panel, "Planning")
        # Side panel needs to be wide enough that all five tab labels can
        # render in full ("Structures" is the widest at ~11px font). 260px
        # is the empirical minimum; below that the tab bar truncates to
        # "S..." even with elide off, because tabs share width equally
        # when setExpanding(True).
        self._side_tabs.setMinimumWidth(260)
        self._side_tabs.setMaximumWidth(480)
        # Show every label in full: turn off scroll-button fallback, turn
        # off ellipsis truncation, and let tabs grow to fit their content
        # instead of squeezing into an equal share.
        self._side_tabs.tabBar().setUsesScrollButtons(False)
        self._side_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self._side_tabs.tabBar().setExpanding(False)
        # Tab styling — selected tab is a bright-green pill so the active
        # panel is unmistakable; padding/min-width are sized so all five
        # labels render fully without ellipsis at the panel's minimum
        # width.
        self._side_tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #2e4a2e; "
            "background: #1e2a1e; top: -1px; }"
            "QTabBar { qproperty-drawBase: 0; background: #122012; }"
            "QTabBar::tab { background: #1a2a1a; color: #90a4ae; "
            "padding: 5px 8px; margin-right: 1px; "
            "border: 1px solid #2e4a2e; border-bottom: none; "
            "border-top-left-radius: 4px; border-top-right-radius: 4px; "
            "font-size: 11px; min-width: 44px; }"
            "QTabBar::tab:hover { background: #284028; color: #c8e6c9; }"
            "QTabBar::tab:selected { background: #2e7d32; color: #ffffff; "
            "font-weight: bold; border: 1px solid #66bb6a; "
            "border-bottom: 2px solid #66bb6a; }"
            "QTabBar::tab:!selected { margin-top: 2px; }"
            "QWidget { background-color: #1e2a1e; color: #c8e6c9; }"
        )

        # Wrap in a CollapsibleSidebar so the entire side panel can be
        # collapsed to a thin chevron strip — replaces the long-standing
        # workaround of "minimize the Design panel" via the splitter.
        self._side_wrapper = CollapsibleSidebar(
            "Side Panel", panel_id="main_sidebar", expanded=True
        )
        self._side_wrapper.set_content(self._side_tabs)

        # Build the left column: Draw toolbar + View toolbar + map.
        # The toolbars used to live in QMainWindow's toolbar area above
        # the central widget; placing them inside the splitter's left
        # column instead lets the right-hand side panel span the full
        # vertical extent (just below the menu bar to just above the
        # status bar) — see Phase 1 of the panel refactor.
        left_col = QWidget(self)
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        self.toolbar.attach_to_layout(left_layout)
        left_layout.addWidget(self.map_widget, 1)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(left_col)
        self._splitter.addWidget(self._side_wrapper)

        # 70 / 30 split
        self._splitter.setSizes([700, 300])
        self._splitter.setStretchFactor(0, 7)
        self._splitter.setStretchFactor(1, 3)

        self.setCentralWidget(self._splitter)

        # Status bar labels
        self._sb_coords  = QLabel("Lat: — , Lng: —")
        self._sb_zone    = QLabel("Zone: —")
        self._sb_mode    = QLabel("Mode: Ready")

        self._sb_coords.setMinimumWidth(220)
        self._sb_zone.setMinimumWidth(100)

        self._sb_tasks = QLabel("")
        self._sb_tasks.setStyleSheet("color: #a5d6a7; font-size: 11px;")
        self._load_seasonal_tasks()

        sb = QStatusBar(self)
        sb.addWidget(self._sb_coords)
        sb.addWidget(_vsep())
        sb.addWidget(self._sb_zone)
        sb.addWidget(_vsep())
        sb.addWidget(self._sb_tasks, 1)
        sb.addPermanentWidget(self._sb_mode)
        self.setStatusBar(sb)

        # Menu bar
        self._build_menu()

        # Recovery hatch: if the saved state restored the sidebar collapsed,
        # the chevron strip on the right edge can be missed entirely. Force
        # the panel open on every launch so users always boot with the panel
        # visible; they can collapse it again from the chevron if they want.
        self._side_wrapper.set_expanded(True, persist=False)
        self._act_show_sidebar.setChecked(True)
        self._side_wrapper.toggled.connect(self._act_show_sidebar.setChecked)

        # Window style
        self.setStyleSheet(_APP_STYLE)

    def _build_plants_polycultures_tab(self) -> QWidget:
        """Build the 'Plants' tab.

        Houses the plant browser/placer and the saved-polyculture library
        under a compact inner tab strip so users can move between the two
        without leaving this outer tab.

        The PlantPanel already owns the inline polyculture-mix builder
        used to place mixes on the map; the PolyculturePanel is for
        editing the saved library of multi-plant templates.
        """
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        from src.ui_style import inner_tab_stylesheet
        inner = QTabWidget(wrap)
        inner.setDocumentMode(True)
        inner.tabBar().setUsesScrollButtons(False)
        inner.tabBar().setExpanding(True)
        inner.setStyleSheet(inner_tab_stylesheet())
        inner.addTab(self.plant_panel, "Plants")
        inner.addTab(self.polyculture_panel, "Plant Communities")
        inner.addTab(self.on_this_design, "On This Design")
        v.addWidget(inner)
        return wrap

    def _on_map_settings(self):
        """View → Map Settings — configure optional map tokens."""
        from src.preferences_dialog import MapPreferencesDialog
        from src.settings import get_mapbox_token, set_mapbox_token
        dlg = MapPreferencesDialog(current_token=get_mapbox_token() or "", parent=self)
        if dlg.exec() == MapPreferencesDialog.DialogCode.Accepted:
            token = dlg.token()
            set_mapbox_token(token)
            if token:
                self.map_widget.set_mapbox_token(token)

    def _on_toggle_sidebar(self, checked: bool):
        """View → Show Side Panel (Ctrl+\\). Mirrors the chevron click."""
        self._side_wrapper.set_expanded(checked)
        if checked:
            # Make sure the splitter actually allocates room for the panel —
            # if it was collapsed via drag, re-expanding the wrapper alone
            # leaves zero width.
            sizes = self._splitter.sizes()
            if len(sizes) >= 2 and sizes[1] < 100:
                total = sum(sizes) or 1000
                self._splitter.setSizes([int(total * 0.7), int(total * 0.3)])

    # ── Update-flow / Help-menu shims ────────────────────────────────────────
    #
    # The implementation lives in src/controllers/update_flow.py
    # (UpdateFlowController, constructed in __init__). These methods stay
    # on MainWindow so that:
    #   • QAction.triggered.connect(self._on_X) wiring in _build_menu and
    #     _connect_signals keeps working without churn,
    #   • tests/test_app_smoke.py's "controller-bound method exists" pins
    #     stay green after the Chunk 5 decomposition.
    # Each shim is a one-line delegate; do not add behaviour here — push
    # it down into the controller.

    # Re-exported for any caller / test that reads it off MainWindow.
    _REPO_RELEASES_URL = UpdateFlowController.REPO_RELEASES_URL

    def _repo_path(self):
        return self._update_flow._repo_path()

    def _current_branch_name(self):
        return self._update_flow._current_branch_name()

    def _on_about(self):
        return self._update_flow._on_about()

    def _on_pick_version(self):
        return self._update_flow._on_pick_version()

    def _on_check_for_updates(self):
        return self._update_flow._on_check_for_updates()

    def _run_update_flow(self, git_runner, *, stash_to_restore):
        return self._update_flow._run_update_flow(
            git_runner, stash_to_restore=stash_to_restore,
        )

    def _maybe_restore_stash(self, git_runner, stash_label):
        return self._update_flow._maybe_restore_stash(git_runner, stash_label)

    def _newest_remote_version_branch(self, git_runner):
        return self._update_flow._newest_remote_version_branch(git_runner)

    def _is_newer_version(self, target, current):
        return self._update_flow._is_newer_version(target, current)

    def _offer_branch_switch(self, git_runner, *, target, current, stash_to_restore):
        return self._update_flow._offer_branch_switch(
            git_runner,
            target=target, current=current,
            stash_to_restore=stash_to_restore,
        )

    def _open_releases_page(self):
        return self._update_flow._open_releases_page()

    def _build_menu(self):
        mb = self.menuBar()

        # Edit menu
        edit_menu = mb.addMenu("&Edit")

        self._act_undo = edit_menu.addAction("&Undo")
        self._act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self._do_undo)

        self._act_redo = edit_menu.addAction("&Redo")
        self._act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self._act_redo.setEnabled(False)
        self._act_redo.triggered.connect(self._do_redo)

        # File menu
        file_menu = mb.addMenu("&File")

        act_new  = file_menu.addAction("&New")
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._on_new)

        act_open = file_menu.addAction("&Open…")
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._on_open)

        file_menu.addSeparator()

        act_save = file_menu.addAction("&Save")
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._on_save)

        act_save_as = file_menu.addAction("Save &As…")
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self._on_save_as)

        file_menu.addSeparator()

        act_generate = file_menu.addAction("&Generate Design…")
        act_generate.setShortcut("Ctrl+G")
        act_generate.setStatusTip(
            "Auto-generate a starting design from your goals "
            "(local AI, with an offline fallback)")
        act_generate.triggered.connect(self._on_generate_design)
        self._act_generate = act_generate

        file_menu.addSeparator()

        act_shopping = file_menu.addAction("Export &Plant Order List…")
        act_shopping.setStatusTip("Export a plant order list grouped by Alberta nursery source")
        act_shopping.triggered.connect(self._on_export_shopping_list)

        act_pdf = file_menu.addAction("Export &PDF…")
        act_pdf.setStatusTip("Export design as a presentation-quality PDF")
        act_pdf.triggered.connect(self._on_export_pdf)

        file_menu.addSeparator()

        act_exit = file_menu.addAction("E&xit")
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)

        # View menu — recovery hatch for users who accidentally collapse the
        # sidebar (the chevron strip on the right edge can be easy to miss).
        view_menu = mb.addMenu("&View")

        self._act_show_sidebar = view_menu.addAction("Show &Side Panel")
        self._act_show_sidebar.setCheckable(True)
        self._act_show_sidebar.setChecked(True)
        self._act_show_sidebar.setShortcut("Ctrl+\\")
        self._act_show_sidebar.setStatusTip(
            "Toggle the right-hand panel (Site / Plants / Analysis / …)"
        )
        self._act_show_sidebar.triggered.connect(self._on_toggle_sidebar)

        view_menu.addSeparator()
        act_map_settings = view_menu.addAction("&Map Settings…")
        act_map_settings.setStatusTip(
            "Configure optional map provider tokens (e.g. Mapbox high-res satellite)"
        )
        act_map_settings.triggered.connect(self._on_map_settings)

        # Help menu
        help_menu = mb.addMenu("&Help")

        # Show the current V<major>.<minor> in the menu item label itself
        # so the user can read it without opening a dialog. The handler
        # opens an About dialog with more detail (commit hash, schema
        # version, etc).
        from src.version_branch import parse_version_branch
        current_branch = self._current_branch_name() or ""
        version_disp = current_branch if parse_version_branch(current_branch) else "dev"
        act_about = help_menu.addAction(f"&About / Version: {version_disp}")
        act_about.setStatusTip(
            "Show the current PermaDesign version, schema version, and "
            "git commit hash"
        )
        act_about.triggered.connect(self._on_about)

        act_update = help_menu.addAction("Check for &Updates…")
        act_update.setStatusTip("Pull the latest version from GitHub (source installs) "
                                "or open the releases page (.exe installs)")
        act_update.triggered.connect(self._on_check_for_updates)

        act_pick = help_menu.addAction("&Switch to a specific version…")
        act_pick.setStatusTip(
            "Pick any published V<major>.<minor> branch and switch the "
            "checkout to it. Handy for rolling back to an older release "
            "or jumping ahead to one the auto-detector doesn't surface."
        )
        act_pick.triggered.connect(self._on_pick_version)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        b = self.map_widget.bridge

        # Map → status bar
        b.mouse_moved.connect(self._on_mouse_moved)

        # Map events → project state (boundary_complete re-connected below with new signature)
        b.plant_placed.connect(self._on_plant_placed)
        b.plant_moved.connect(self._on_plant_moved)
        b.plant_group_moved.connect(self._on_plant_group_moved)
        b.map_ready.connect(self._on_map_ready)

        # Toolbar → map
        self.toolbar.draw_boundary_requested.connect(self._enter_boundary_mode)
        self.toolbar.measure_requested.connect(self._enter_measure_mode)
        self.toolbar.annotate_requested.connect(self._enter_annotate_mode)
        self.toolbar.cancel_draw_requested.connect(self._cancel_draw)
        self.toolbar.undo_requested.connect(self._do_undo)

        self.toolbar.satellite_toggled.connect(self.map_widget.set_satellite_visible)
        self.toolbar.boundary_toggled.connect(self.map_widget.set_boundary_visible)
        self.toolbar.measurements_toggled.connect(
            self.map_widget.set_measurements_visible
        )
        self.toolbar.plants_toggled.connect(self.map_widget.set_plants_visible)
        self.toolbar.canopy_toggled.connect(self.map_widget.set_canopy_visible)
        self.toolbar.grid_settings_changed.connect(self._on_grid_settings_changed)

        # Plant panel → map (plant placement + colour). Pattern mode info
        # arrives in the 4th argument; legacy single-mode placements pass
        # {"kind": "single"}.
        self.plant_panel.place_plant_requested.connect(self._enter_plant_mode)
        self.plant_panel.color_changed.connect(self._on_plant_color_changed)

        # Map → remove plant marker
        b.plant_removed.connect(self._on_plant_removed)

        # Map → batch placement (Burst, Row, Grid, Circle)
        b.pattern_placed.connect(self._on_pattern_placed)

        # Map → annotations
        b.annotate_requested.connect(self._on_annotate_requested)
        b.annotation_removed.connect(self._on_annotation_removed)

        # Polyculture panel → map (polyculture placement)
        self.polyculture_panel.placePolycultureRequested.connect(self._enter_polyculture_mode)
        # Stack → community: refresh the Communities tree when the Plants
        # tab (or anywhere else) creates a brand-new plant community.
        self.plant_panel.communityCreated.connect(
            self.polyculture_panel._refresh_polyculture_list
        )
        self.polyculture_panel.communityCreated.connect(
            self.polyculture_panel._refresh_polyculture_list
        )
        # Mirror plant_panel's per-species counts into the sibling
        # On-This-Design tab's Plants sub-tab.
        self.plant_panel.placed_counts_changed.connect(
            lambda: self.on_this_design.set_plants_counts(
                self.plant_panel._placed_counts
            )
        )

        # Structure panel → map
        self.structure_panel.place_structure_requested.connect(self._enter_structure_mode)
        self.structure_panel.place_hedgerow_requested.connect(self._enter_hedgerow_mode)
        self.structure_panel.place_shape_requested.connect(self._enter_shape_mode)

        # Map → structures/hedgerows/shapes
        b.structure_placed.connect(self._on_structure_placed)
        b.structure_removed.connect(self._on_structure_removed)
        b.hedgerow_complete.connect(self._on_hedgerow_complete)
        b.hedgerow_removed.connect(self._on_hedgerow_removed)
        b.shape_complete.connect(self._on_shape_complete)
        b.shape_removed.connect(self._on_shape_removed)
        b.shape_height_changed.connect(self._on_shape_height_changed)
        b.shape_geom_changed.connect(self._on_shape_geom_changed)

        # Toolbar → structures layer toggle
        self.toolbar.structures_toggled.connect(self.map_widget.set_structures_visible)

        # Analysis panel → map (A1-A4)
        self.analysis_panel.sun_path_requested.connect(self._on_sun_path_requested)
        self.analysis_panel.sun_path_cleared.connect(self.map_widget.clear_sun_path)
        self.analysis_panel.sector_requested.connect(self._on_sector_requested)
        self.analysis_panel.sector_cleared.connect(self.map_widget.clear_sectors)
        # (Manual contour drawing moved to Site panel — wired below.)
        # Auto-terrain controls live on the Site panel now (alongside the
        # single-point Elevation/slope readout) — the request / clear /
        # opacity signals come from there.
        self.site_panel.auto_terrain_requested.connect(self._on_auto_terrain_requested)
        self.site_panel.auto_terrain_cleared.connect(self._on_auto_terrain_cleared)
        self.site_panel.auto_terrain_opacity.connect(self.map_widget.set_slope_overlay_opacity)
        b.terrain_bbox_ready.connect(self._on_terrain_bbox_ready)
        b.terrain_bbox_cancelled.connect(self._on_terrain_bbox_cancelled)
        self.site_panel.download_edmonton_requested.connect(
            self._on_download_edmonton_requested
        )
        # Shade overlay + OSM import (V1.51).
        self.site_panel.shade_requested.connect(self._on_shade_requested)
        self.site_panel.shade_cleared.connect(self._on_shade_cleared)
        self.site_panel.shade_opacity.connect(self._on_shade_opacity)
        self.site_panel.shade_zones_requested.connect(self._on_shade_zones_requested)
        self.site_panel.osm_import_requested.connect(self._on_osm_import_requested)
        self.site_panel.footprint_import_requested.connect(
            self._on_footprint_import_requested)
        # Shade sub-tab: mark/draw existing trees & buildings (relocated from
        # the Structures panel) — reuse the structure/shape placement pipeline.
        self.site_panel.place_structure_requested.connect(
            self._enter_structure_mode)
        self.site_panel.place_shape_requested.connect(self._enter_shape_mode)
        # Satellite imagery alignment nudge → shift the basemap tiles (cosmetic).
        self.site_panel.satellite_offset_changed.connect(
            self.map_widget.set_satellite_offset)
        self.analysis_panel.wind_requested.connect(self._on_wind_requested)
        self.analysis_panel.wind_cleared.connect(self.map_widget.clear_wind_overlay)
        self.analysis_panel.season_changed.connect(self._on_season_changed)

        # Map → polyculture removal
        b.polyculture_removed.connect(self._on_polyculture_removed)

        # Map → contour complete / removal
        b.contour_complete.connect(self._on_contour_complete)
        b.contour_removed.connect(self._on_contour_removed)

        # Map → multi-boundary events
        b.boundary_complete.connect(self._on_boundary_complete)
        b.boundary_geom_changed.connect(self._on_boundary_geom_changed)
        b.boundary_props_changed.connect(self._on_boundary_props_changed)
        b.boundary_removed.connect(self._on_boundary_removed)

        # Map → sun path / sector anchor & removal
        b.sun_anchor_placed.connect(self._on_sun_anchor_placed)
        b.sun_path_removed.connect(self._on_sun_path_removed)
        b.anchor_cancelled.connect(self._on_anchor_cancelled)
        b.sector_anchor_placed.connect(self._on_sector_anchor_placed)
        b.sector_group_removed.connect(self._on_sector_group_removed)
        b.sector_group_moved.connect(self._on_sector_group_moved)
        b.sector_group_rotated.connect(self._on_sector_group_rotated)
        b.sector_group_resized.connect(self._on_sector_group_resized)

        # Toolbar → zoom sensitivity
        self.toolbar.zoom_step_changed.connect(self.map_widget.set_zoom_sensitivity)

        # Planning panel → timeline / notes
        self.planning_panel.timeline_year_changed.connect(self._on_timeline_year_changed)
        self.planning_panel.notes_changed.connect(self._on_notes_changed)

        # Site panel ↔ map
        b.site_pin_placed.connect(self._on_site_pin_placed)
        b.site_pin_removed.connect(self._on_site_pin_removed)
        self.site_panel.pin_drop_requested.connect(self._enter_site_pin_mode)
        self.site_panel.pin_clear_requested.connect(self._on_site_pin_clear_clicked)
        self.site_panel.site_data_updated.connect(self._on_site_data_updated)
        # Address search → drop pin on map (the bridge then notifies us
        # back via site_pin_placed and the usual fetch flow runs).
        self.site_panel.address_resolved.connect(self._on_address_resolved)
        # Manual contour drawing controls live on the Site tab now.
        self.site_panel.contour_requested.connect(self._on_contour_requested)
        self.site_panel.contour_cleared.connect(self._on_contour_cleared)

    # ── Map-ready ─────────────────────────────────────────────────────────────

    def _on_map_ready(self):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_map_ready()

    def _on_plant_color_changed(self, plant_id: int, hex_color: str):
        """Update all existing markers for this plant on the map."""
        self.map_widget.update_marker_color(plant_id, hex_color)

    # ── Status bar updates ────────────────────────────────────────────────────

    def _on_mouse_moved(self, lat: float, lng: float):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_mouse_moved(lat, lng)

    def _set_zone_display(self, zone):
        self._current_zone = zone
        self._sb_zone.setText(zone_label(zone))
        self._project["properties"]["hardiness_zone"] = zone
        self.plant_panel.set_zone(zone)

    def _on_grid_settings_changed(self, settings: dict):
        """Apply changes from the View bar's Grid menu — enabled/size/style."""
        try:
            self.map_widget.set_snap_enabled(
                bool(settings.get("enabled")),
                float(settings.get("size_m") or 1.0),
            )
        except Exception:
            pass
        color = settings.get("color")
        opacity = settings.get("opacity")
        if color is not None or opacity is not None:
            try:
                self.map_widget.set_grid_style(
                    str(color or "#4a7a4a"),
                    float(opacity if opacity is not None else 0.4),
                )
            except Exception:
                pass

    def _set_mode_label(self, text: str):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._set_mode_label(text)

    def _mark_modified(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._mark_modified()

    # ── Seasonal tasks ────────────────────────────────────────────────────────

    def _load_seasonal_tasks(self):
        """Show current month's planting tasks in the status bar."""
        try:
            from src.db.plants import get_current_month_tasks
            from datetime import datetime
            month_name = datetime.now().strftime("%B")
            tasks = get_current_month_tasks()
            if tasks:
                # Group by status
                by_status = {}
                for t in tasks[:8]:  # Limit to avoid overflow
                    s = t["status"].replace("_", " ").title()
                    by_status.setdefault(s, []).append(t["common_name"])
                parts = []
                for status, names in by_status.items():
                    parts.append(f"{status}: {', '.join(names[:3])}")
                    if len(names) > 3:
                        parts[-1] += f" +{len(names)-3}"
                self._sb_tasks.setText(f"{month_name}: {' | '.join(parts)}")
            else:
                self._sb_tasks.setText(f"{month_name}: No active tasks")
        except Exception:
            pass

    # ── Drawing modes ─────────────────────────────────────────────────────────

    def _enter_boundary_mode(self):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_boundary_mode()

    def _enter_plant_mode(self, plant_id: int, common_name: str,
                          quantity: int = 1, pattern: dict | None = None):
        self._current_mode = 'plant'
        # Clear any stale community-pattern stash from a previous
        # community placement; _enter_polyculture_pattern_mode will
        # re-set it after this call returns if a community is being
        # placed, otherwise plant-only patterns get the plant branch.
        self._pending_community_pattern = None
        self._pending_community_pattern_mix = None
        spacing_m, plant_type, custom_color = self._plant_info(plant_id)

        # Polyculture override: when the panel built a mix recipe, use
        # the resolved effective spacing (default = max canopy width)
        # so the JS-side geometry generator lays out cells at a step
        # that fits the largest species in the mix.
        poly = ((pattern or {}).get("params") or {}).get("polyculture")
        if poly and poly.get("effective_spacing_m"):
            spacing_m = float(poly["effective_spacing_m"])

        try:
            from src.db.plants import get_plant
            _p = get_plant(plant_id)
            mature_canopy_m = (_p or {}).get("mature_canopy_m")
        except Exception:
            mature_canopy_m = None

        self.map_widget.set_mode('plant', plant_id, common_name, spacing_m,
                                 plant_type, quantity, custom_color,
                                 pattern=pattern,
                                 mature_canopy_m=mature_canopy_m)
        self.toolbar.enter_plant_mode()

        kind = (pattern or {}).get("kind", "single")
        species_n = len(poly["species"]) if poly else 0
        poly_tag = f" · Mix ({species_n} species)" if species_n else ""
        # When a polyculture is armed, the recipe persists until Esc, so
        # advertise that the user can drop multiple identical patterns.
        tail = " (Esc to finish)" if poly else " — Esc to cancel"
        if kind == "single":
            qty_str = f" ×{quantity}" if quantity > 1 else ""
            label = f"Placing: {common_name}{qty_str} — click map, press Esc to cancel"
        elif kind == "row":
            label = f"Row of {common_name}{poly_tag} — click start point, then end point{tail}"
        elif kind == "grid":
            label = f"Grid of {common_name}{poly_tag} — click two opposite corners{tail}"
        elif kind == "circle":
            label = f"Circle of {common_name}{poly_tag} — click centre, then radius point{tail}"
        else:
            label = f"Placing: {common_name}"
        self._set_mode_label(label)

    @staticmethod
    def _plant_info(plant_id: int) -> tuple[float, str, str]:
        """Return (spacing_meters, plant_type, marker_color) for a plant."""
        try:
            from src.db.plants import get_plant
            p = get_plant(plant_id)
            if p:
                return (
                    float(p.get("spacing_meters") or 1.0),
                    p.get("plant_type") or "herb",
                    p.get("marker_color") or "",
                )
        except Exception:
            pass
        return 1.0, "herb", ""

    def _enter_measure_mode(self):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_measure_mode()

    def _enter_annotate_mode(self):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_annotate_mode()

    # Annotation handlers — shims → MapEventRouter.

    def _on_annotate_requested(self, lat: float, lng: float):
        return self._map_events._on_annotate_requested(lat, lng)

    def _on_annotation_removed(self, ann_id: str):
        return self._map_events._on_annotation_removed(ann_id)

    # ── Structure / Hedgerow / Shape modes ──────────────────────────────────

    def _enter_structure_mode(self, struct_def: dict):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_structure_mode(struct_def)

    # Structure handlers — shims → MapEventRouter; see src/controllers/map_events.py.

    def _on_structure_placed(self, struct_id: str, name: str, lat: float,
                              lng: float, size_m: float):
        return self._map_events._on_structure_placed(
            struct_id, name, lat, lng, size_m,
        )

    def _on_structure_removed(self, marker_id: str, struct_id: str,
                               lat: float, lng: float):
        return self._map_events._on_structure_removed(
            marker_id, struct_id, lat, lng,
        )

    def _enter_hedgerow_mode(self, hedge_config: dict):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_hedgerow_mode(hedge_config)

    # Hedgerow handlers — shims → MapEventRouter; see src/controllers/map_events.py.

    def _on_hedgerow_complete(self, hedge_id: str, points_json: str,
                               species: str, style: str, length_m: float,
                               num_plants: int):
        return self._map_events._on_hedgerow_complete(
            hedge_id, points_json, species, style, length_m, num_plants,
        )

    def _on_hedgerow_removed(self, hedge_id: str, points_json: str):
        return self._map_events._on_hedgerow_removed(hedge_id, points_json)

    def _enter_shape_mode(self, shape_config: dict):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_shape_mode(shape_config)

    # Shape handlers — shims → MapEventRouter; see src/controllers/map_events.py.

    def _on_shape_complete(self, shape_id: str, points_json: str, label: str,
                            shape_type: str, fill_color: str, stroke_color: str,
                            fill_opacity: float, dash_array: str, area_m2: float,
                            height_m: float = 0.0):
        return self._map_events._on_shape_complete(
            shape_id, points_json, label, shape_type,
            fill_color, stroke_color, fill_opacity, dash_array, area_m2,
            height_m,
        )

    def _on_shape_removed(self, shape_id: str):
        return self._map_events._on_shape_removed(shape_id)

    def _on_shape_height_changed(self, shape_id: str, height_m: float):
        return self._map_events._on_shape_height_changed(shape_id, height_m)

    def _on_shape_geom_changed(self, shape_id: str, points: list):
        return self._map_events._on_shape_geom_changed(shape_id, points)

    # ── Analysis overlays (A1-A4) ──────────────────────────────────────────

    def _on_sun_path_requested(self, config: dict):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_sun_path_requested(config)

    def _render_sun_path(self, config: dict, lat: float, lng: float):
        """Compute sun positions and send to JS with the clicked anchor."""
        from datetime import date as _date
        from src.solar import sun_path_for_date, sunrise_sunset

        d = _date.fromisoformat(config["date"])
        positions = sun_path_for_date(lat, lng, d, steps=72)
        sr, ss = sunrise_sunset(lat, lng, d)

        pos_data = [
            {"altitude": p.altitude, "azimuth": p.azimuth, "hour": p.hour}
            for p in positions
        ]

        payload = {
            "positions": pos_data,
            "date_label": config.get("date_label", d.isoformat()),
            "show_shadows": config.get("show_shadows", True),
            "show_shadow_length": config.get("show_shadow_length", False),
            "sunrise_hour": sr,
            "sunset_hour": ss,
        }
        if "arc_radius" in config:
            payload["arc_radius"] = config["arc_radius"]
        self.map_widget.draw_sun_path(payload, lat, lng)

        noon_alt = max((p.altitude for p in positions), default=0)
        daylight = ss - sr
        self.analysis_panel.set_sun_info(
            f"Sunrise: {_fmt_time(sr)} | Sunset: {_fmt_time(ss)}\n"
            f"Daylight: {daylight:.1f} hrs | Max altitude: {noon_alt:.1f}°"
        )
        self._set_mode_label(f"Sun path: {config.get('date_label', d.isoformat())}")
        self._pending_sun_config = None

    def _on_sector_requested(self, config: dict):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_sector_requested(config)

    def _on_contour_requested(self, config: dict):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_contour_requested(config)

    # Contour handlers — shims → MapEventRouter.

    def _on_contour_complete(self, points_json: str, elevation: float,
                              color: str):
        return self._map_events._on_contour_complete(points_json, elevation, color)

    def _on_contour_removed(self, points_json: str, elevation: float,
                             color: str):
        return self._map_events._on_contour_removed(points_json, elevation, color)

    def _on_contour_cleared(self):
        return self._map_events._on_contour_cleared()

    # ── Auto-generated terrain (slope contours + ramp overlay) ────────────────

    # ── Auto-terrain pipeline — shims → MapEventRouter ────────────────────────
    # Implementation in src/controllers/map_events.py. Helpers like
    # _maybe_start_next_terrain_job are referenced by name from
    # QTimer.singleShot() inside the controller, so they live on
    # MainWindow as shims that delegate down.

    def _on_auto_terrain_requested(self, config: dict):
        return self._map_events._on_auto_terrain_requested(config)

    def _on_terrain_bbox_cancelled(self):
        return self._map_events._on_terrain_bbox_cancelled()

    def _on_terrain_bbox_ready(self, bbox: dict):
        return self._map_events._on_terrain_bbox_ready(bbox)

    def _maybe_start_next_terrain_job(self):
        return self._map_events._maybe_start_next_terrain_job()

    def _terrain_queue_prefix(self) -> str:
        return self._map_events._terrain_queue_prefix()

    def _update_terrain_queue_status(self):
        return self._map_events._update_terrain_queue_status()

    def _on_terrain_thread_done(self):
        return self._map_events._on_terrain_thread_done()

    def _on_terrain_ready(self, result: dict):
        return self._map_events._on_terrain_ready(result)

    def _on_terrain_failed(self, message: str):
        return self._map_events._on_terrain_failed(message)

    def _on_auto_terrain_cleared(self):
        return self._map_events._on_auto_terrain_cleared()

    # ── Shade overlay + OSM import (V1.51) — shims → MapEventRouter ───────────

    def _on_shade_requested(self, config: dict):
        return self._map_events._on_shade_requested(config)

    def _on_shade_cleared(self):
        return self._map_events._on_shade_cleared()

    def _on_shade_opacity(self, opacity: float):
        return self._map_events._on_shade_opacity(opacity)

    def _on_shade_zones_requested(self):
        return self._map_events._on_shade_zones_requested()

    def _on_osm_import_requested(self):
        return self._map_events._on_osm_import_requested()

    def _on_footprint_import_requested(self, tiff_path: str):
        return self._map_events._on_footprint_import_requested(tiff_path)

    # ── Edmonton offline download — shims → MapEventRouter ───────────────────

    def _on_download_edmonton_requested(self):
        return self._map_events._on_download_edmonton_requested()

    def _on_edmonton_dl_progress(self, features_stored: int, page_num: int,
                                   text: str):
        return self._map_events._on_edmonton_dl_progress(
            features_stored, page_num, text,
        )

    def _on_edmonton_dl_finished(self, total: int):
        return self._map_events._on_edmonton_dl_finished(total)

    def _on_edmonton_dl_error(self, message: str):
        return self._map_events._on_edmonton_dl_error(message)

    def _on_dl_thread_done(self):
        return self._map_events._on_dl_thread_done()

    def _on_wind_requested(self, config: dict):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_wind_requested(config)

    def _on_season_changed(self, season: str):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_season_changed(season)

    def _enter_polyculture_mode(self, polyculture_data: dict):
        """Place a polyculture on the map.

        Two modes:
          - "single" (no pattern, or pattern.kind == "single"): click once
            to drop the community at the clicked point. Each member is
            placed at its offset_x/offset_y from that centre.
          - "row" / "grid" / "circle": enter plant-pattern mode with a
            synthetic representative plant (so JS's preview ghost works),
            stash the full community, and let JS handle the 2-click
            gesture. The stashed community is expanded across the
            resulting anchor positions in _on_pattern_placed.
        """
        pattern = polyculture_data.get("pattern")
        kind = (pattern or {}).get("kind") or "single"
        if kind != "single" and polyculture_data.get("members"):
            self._enter_polyculture_pattern_mode(polyculture_data, pattern)
            return

        self._current_mode = 'polyculture'
        self._pending_polyculture = polyculture_data
        self.map_widget.set_crosshair_cursor()
        self._set_mode_label(
            f"Placing plant community: {polyculture_data.get('name', '?')} — click map to place centre"
        )
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_polyculture_click)
        except TypeError:
            pass
        self.map_widget.bridge.map_clicked.connect(self._on_polyculture_click)

    def _enter_polyculture_pattern_mode(self, polyculture_data: dict, pattern: dict):
        """Set up row/grid/circle placement of a community as a unit.

        Reuses plant-pattern mode by picking the member closest to (0,0)
        as the synthetic preview plant. The full community is stashed
        in self._pending_community_pattern so _on_pattern_placed can
        expand each anchor position into one full community.
        """
        members = polyculture_data.get("members") or []
        # Pick the member nearest the community centre as the preview anchor.
        members_sorted = sorted(
            members,
            key=lambda m: (float(m.get("offset_x") or 0.0) ** 2
                           + float(m.get("offset_y") or 0.0) ** 2),
        )
        primary = members_sorted[0]
        primary_pid = int(primary["plant_id"])
        primary_name = primary.get("common_name") or polyculture_data.get("name", "")

        spacing_m = float(pattern.get("spacing_m") or 4.0)
        kind = pattern.get("kind") or "row"

        # Use the params dict the placement widget produced. Defaults
        # cover legacy callers that supplied only kind + spacing_m.
        params = dict(pattern.get("params") or {})
        params.setdefault("overlap", 0.0)
        params.setdefault("use_canopy", False)
        # Detect the community-mix case (Plants tab analogue: one stack
        # of multiple communities at ratios). Each anchor will become one
        # full community, picked according to the ratios.
        community_mix = params.pop("community_mix", None)
        # Carry the full community payload so _on_pattern_placed can
        # expand each anchor into the community's members.
        params["community"] = {
            "name": polyculture_data.get("name", ""),
            "spacing_m": spacing_m,
            "members": [dict(m) for m in members],
        }
        pattern_dict = {"kind": kind, "params": params}

        # Drop any stale plant-mix recipe so it doesn't get applied.
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass
        self._enter_plant_mode(primary_pid, primary_name,
                               quantity=1, pattern=pattern_dict)
        # Stash AFTER _enter_plant_mode (which clears the previous stash
        # at its top) so this fresh community is the one expanded by
        # _on_pattern_placed. The mix stash takes precedence over the
        # single-community stash when present.
        self._pending_community_pattern = pattern_dict["params"]["community"]
        self._pending_community_pattern_mix = community_mix
        # Override the mode label so the user sees the community context.
        if community_mix:
            community_name = (
                f"{len(community_mix)}-community mix "
                f"({':'.join(str(c['weight']) for c in community_mix)})"
            )
        else:
            community_name = polyculture_data.get("name", "?")
        gesture = {
            "row":    "click start, then end",
            "grid":   "click two opposite corners",
            "circle": "click centre, then radius point",
        }.get(kind, "click")
        self._set_mode_label(
            f"Placing community '{community_name}' as {kind} — {gesture}. "
            "Esc to cancel."
        )

    def _on_polyculture_click(self, lat: float, lng: float):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_polyculture_click(lat, lng)

    def _cancel_draw(self):
        self._current_mode = 'none'
        self.map_widget.cancel_draw()
        # Also bail out of an armed manual pin-drop, since Esc / Cancel
        # is the user's universal "back out" gesture.
        if getattr(self, "_site_pin_mode", False):
            self._site_pin_mode = False
            self.map_widget.set_site_pin_drop_mode(False)
            try:
                self.map_widget.bridge.map_clicked.disconnect(
                    self._on_site_pin_click
                )
            except (TypeError, RuntimeError):
                pass
        self._set_mode_label("Ready")
        self.toolbar.reset_draw_buttons()
        # Drop any in-flight polyculture recipe — the user explicitly
        # exited plant mode, so the next Place Mix click should re-stash
        # a fresh one.
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass
        # Same idea for any community-pattern stash: dropping it on
        # cancel ensures the user starts fresh next time they hit Place.
        self._pending_community_pattern = None
        self._pending_community_pattern_mix = None

    # ── Map event handlers ────────────────────────────────────────────────────

    # ── Boundary handlers — shims → MapEventRouter ────────────────────────────
    # Implementation in src/controllers/map_events.py. The method names stay
    # on MainWindow so the QSignal.connect() bindings in _connect_signals
    # (lines ~643-646) keep working without churn.

    def _on_boundary_complete(self, bid: str, coords: list, color: str):
        return self._map_events._on_boundary_complete(bid, coords, color)

    def _on_boundary_geom_changed(self, bid: str, coords: list):
        return self._map_events._on_boundary_geom_changed(bid, coords)

    def _on_boundary_props_changed(self, bid: str, color: str,
                                    show_lengths: bool, show_area: bool):
        return self._map_events._on_boundary_props_changed(
            bid, color, show_lengths, show_area,
        )

    def _on_boundary_removed(self, bid: str):
        return self._map_events._on_boundary_removed(bid)

    # Plant move handlers — shims → MapEventRouter.

    def _on_plant_moved(self, marker_id: str, plant_id: int,
                        old_lat: float, old_lng: float,
                        new_lat: float, new_lng: float):
        return self._map_events._on_plant_moved(
            marker_id, plant_id, old_lat, old_lng, new_lat, new_lng,
        )

    def _on_plant_group_moved(self, group_id: str,
                              originals_json: str, moved_json: str):
        return self._map_events._on_plant_group_moved(
            group_id, originals_json, moved_json,
        )

    # Sun-path / sector anchor handlers — shims → MapEventRouter.

    def _on_sun_anchor_placed(self, lat: float, lng: float):
        return self._map_events._on_sun_anchor_placed(lat, lng)

    def _on_sector_anchor_placed(self, lat: float, lng: float):
        return self._map_events._on_sector_anchor_placed(lat, lng)

    def _on_sun_path_removed(self):
        return self._map_events._on_sun_path_removed()

    def _on_anchor_cancelled(self, mode: str):
        return self._map_events._on_anchor_cancelled(mode)

    def _on_sector_group_removed(self, sid: str):
        return self._map_events._on_sector_group_removed(sid)

    def _on_sector_group_moved(self, sid: str, lat: float, lng: float):
        return self._map_events._on_sector_group_moved(sid, lat, lng)

    def _on_sector_group_rotated(self, sid: str, rotation_deg: float):
        return self._map_events._on_sector_group_rotated(sid, rotation_deg)

    def _on_sector_group_resized(self, sid: str, radius_m: float):
        return self._map_events._on_sector_group_resized(sid, radius_m)

    def _on_plant_placed(self, plant_id: int, common_name: str, lat: float, lng: float):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_plant_placed(plant_id, common_name, lat, lng)

    def _on_generate_design(self):
        # Shim → GenerationController; see src/controllers/generation.py.
        return self._generation.open_dialog()

    def _expand_communities_at_positions(self, positions, community: dict,
                                          pattern_kind: str):
        """Expand a Community across N anchor positions.

        ``community`` is the dict stashed in self._pending_community_pattern
        by _enter_polyculture_pattern_mode (or a single-community block).
        Currently always uses the same community at every anchor — the
        community-mix (ratio) variant can plug in here later by replacing
        the single dict with per-anchor assignments.

        Every placed marker across every anchor shares a single
        placement_group_id, so deleting any marker via "Delete group"
        removes the whole pattern. The per-anchor polyculture_name +
        polyculture_center_{lat,lng} are also written so
        _on_polyculture_removed can target one community at a time.
        """
        import math
        members = community.get("members") or []
        if not members or not positions:
            return

        poly_name = community.get("name") or ""
        group_id = project_io.new_placement_group_id()

        batch_placements: list[tuple[int, str]] = []
        for (lat, lng) in positions:
            cos_lat = math.cos(lat * math.pi / 180) or 1e-9
            community_id = project_io.community_id_for(lat, lng)
            for m in members:
                pid = m["plant_id"]
                name = m.get("common_name", "")
                spacing_m, plant_type, _ = self._plant_info(pid)
                color = _member_color(m)
                mlat = lat + float(m.get("offset_y", 0) or 0) / 111320
                mlng = lng + float(m.get("offset_x", 0) or 0) / (111320 * cos_lat)

                self.map_widget.place_plant_marker(
                    pid, name, mlat, mlng,
                    spacing_m=spacing_m, plant_type=plant_type,
                    color=color, group_id=group_id, community_id=community_id,
                )
                self._placed_plants.append({
                    "plant_id": pid, "common_name": name,
                    "lat": mlat, "lng": mlng,
                    "polyculture_name": poly_name,
                    "polyculture_center_lat": lat,
                    "polyculture_center_lng": lng,
                    "placement_group_id": group_id,
                })
                self._project["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [mlng, mlat]},
                    "properties": {
                        "element_type": "plant",
                        "plant_id": pid,
                        "common_name": name,
                        "polyculture_name": poly_name,
                        "polyculture_center_lat": lat,
                        "polyculture_center_lng": lng,
                        "placement_group_id": group_id,
                        "pattern_kind": pattern_kind,
                        "quantity": 1,
                    }
                })
                batch_placements.append((pid, name))

        self.plant_panel.on_plants_placed_batch(batch_placements)
        self._mark_modified()
        self._sync_planning_panel()
        self._set_mode_label(
            f"Placed {len(positions)} × '{poly_name}' ({pattern_kind}). "
            "Click again for another, or press Esc to finish."
        )
        self.statusBar().showMessage(
            f"Placed {len(positions)} communities of '{poly_name}' "
            f"({len(members)} members each)",
            3000,
        )

    def _on_pattern_placed(self, plant_id: int, common_name: str,
                            spacing_m: float, plant_type: str,
                            custom_color: str, positions_json: str,
                            pattern_kind: str):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_pattern_placed(
            plant_id, common_name, spacing_m, plant_type,
            custom_color, positions_json, pattern_kind,
        )

    def _on_plant_removed(self, marker_id: str, plant_id: int, lat: float, lng: float):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_plant_removed(marker_id, plant_id, lat, lng)

    def _on_polyculture_removed(self, polyculture_name: str,
                                  center_lat: float, center_lng: float):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_polyculture_removed(
            polyculture_name, center_lat, center_lng,
        )

    # ── Site pin / property data ──────────────────────────────────────────────

    # Site-pin handlers — shims → MapEventRouter.

    def _on_site_pin_placed(self, lat: float, lng: float, label: str):
        return self._map_events._on_site_pin_placed(lat, lng, label)

    def _on_site_pin_removed(self):
        return self._map_events._on_site_pin_removed()

    def _on_site_pin_clear_clicked(self):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_site_pin_clear_clicked()

    def _on_address_resolved(self, lat: float, lng: float, label: str):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_address_resolved(lat, lng, label)

    def _enter_site_pin_mode(self):
        """Manual pin-drop: next map click places the pin."""
        self._site_pin_mode = True
        self._set_mode_label("Click the map to drop the property pin")
        # Visual affordance — switch the map cursor to a crosshair so the
        # user can see that the next click is going to drop a point.
        self.map_widget.set_site_pin_drop_mode(True)
        # One-shot connection to map_clicked
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_site_pin_click)
        except Exception:
            pass
        self.map_widget.bridge.map_clicked.connect(self._on_site_pin_click)

    def _on_site_pin_click(self, lat: float, lng: float):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_site_pin_click(lat, lng)

    def _start_pin_reverse_geocode(self, lat: float, lng: float):
        """Look up the actual address for a manually-dropped pin.

        Runs Nominatim's reverse geocode off the UI thread; if it
        succeeds we re-place the pin with the resolved label so the Site
        panel shows a real address instead of just lat/lng.
        """
        # Cancel any prior reverse-geocode worker first.
        prev_worker = getattr(self, "_revgeo_worker", None)
        prev_thread = getattr(self, "_revgeo_thread", None)
        self._revgeo_worker = None
        self._revgeo_thread = None
        if prev_worker is not None:
            try:
                prev_worker.results.disconnect()
            except (TypeError, RuntimeError):
                pass
        # Use the same safe-isRunning pattern as site_panel — calling
        # isRunning() on a QThread whose C++ side has been deleteLater'd
        # raises RuntimeError, which used to crash the app on rapid
        # consecutive pin actions.
        from src.site_panel import _safe_is_running as _safe_is_running_thread
        if _safe_is_running_thread(prev_thread):
            try:
                prev_thread.quit()
            except RuntimeError:
                pass

        from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

        class _RevGeoWorker(QObject):
            results = pyqtSignal(float, float, str)  # lat, lng, label ("" on fail)

            def __init__(self, lat: float, lng: float):
                super().__init__()
                self._lat = lat
                self._lng = lng

            @pyqtSlot()
            def run(self):
                try:
                    from src.property_data import reverse_geocode
                    label = reverse_geocode(self._lat, self._lng) or ""
                except Exception:
                    label = ""
                self.results.emit(self._lat, self._lng, label)

        thread = QThread(self)
        worker = _RevGeoWorker(lat, lng)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.results.connect(self._on_pin_reverse_geocode_done)
        # Auto-teardown chain (same pattern as site_panel._start_fetch).
        worker.results.connect(thread.quit)
        worker.results.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._revgeo_worker = worker
        self._revgeo_thread = thread
        thread.start()

    def _on_pin_reverse_geocode_done(self, lat: float, lng: float, label: str):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_pin_reverse_geocode_done(lat, lng, label)

    def _on_site_data_updated(self, result: dict):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_site_data_updated(result)

    # ── File operations ───────────────────────────────────────────────────────

    def _on_new(self):
        if self._modified:
            r = QMessageBox.question(
                self, "New Design",
                "Current design has unsaved changes. Discard and start new?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            if r != QMessageBox.StandardButton.Yes:
                return

        name, ok = QInputDialog.getText(
            self, "New Design", "Project name:", text="My Food Forest"
        )
        if not ok:
            return
        name = name.strip() or "Untitled Design"

        self._project      = project_io.new_project(name)
        self._project_path = None
        self._modified     = False
        self._placed_plants.clear()
        self._clear_undo()
        self._current_zone = None
        self._sb_zone.setText("Zone: —")
        self.map_widget.clear_all()
        self.map_widget.clear_site_pin()
        self.site_panel.clear_pin()
        self.plant_panel.clear_placed()
        self.plant_panel.set_zone(None)
        self.planning_panel.set_notes("")
        self.planning_panel.set_placed_plants([])
        self.planning_panel.set_structures([])
        self.analysis_panel.set_placed_plants([])
        self.analysis_panel.set_structures([])
        self.setWindowTitle(f"PermaDesign — {name}")
        self._set_mode_label("Ready")

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Design", "",
            "PermaDesign Files (*.perma.geojson);;GeoJSON (*.geojson);;All files (*)"
        )
        if not path:
            return
        try:
            self._load_from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _load_from_path(self, path: str):
        proj = project_io.load_project(path)
        self._project      = proj
        self._project_path = path
        self._modified     = False
        self._placed_plants.clear()
        self._clear_undo()

        self.map_widget.clear_all()
        data = project_io.project_to_map_data(proj)

        for bd in data.get("boundaries", []):
            self.map_widget.load_boundary(bd)
        if data.get("boundaries"):
            first = data["boundaries"][0]
            lats = [p[0] for p in first["points"]]
            lngs = [p[1] for p in first["points"]]
            self._set_zone_display(
                get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs))
            )

        # Backfill placement_group_id onto legacy project features so that a
        # subsequent save persists them. project_to_map_data already minted
        # singleton groups for any feature that lacked one.
        plant_idx = 0
        for f in proj.get("features", []):
            if f.get("properties", {}).get("element_type") == "plant":
                if not f["properties"].get("placement_group_id") and plant_idx < len(data["plants"]):
                    f["properties"]["placement_group_id"] = (
                        data["plants"][plant_idx]["placement_group_id"]
                    )
                plant_idx += 1

        for p in data["plants"]:
            spacing_m, plant_type, custom_color = self._plant_info(p["plant_id"])
            community_id = project_io.community_id_for(
                p.get("polyculture_center_lat"), p.get("polyculture_center_lng")
            )
            self.map_widget.load_plant_marker(
                p["plant_id"], p["common_name"], p["lat"], p["lng"],
                spacing_m, plant_type, custom_color,
                p.get("placement_group_id", ""),
                community_id or "",
            )
            self._placed_plants.append(p)

        self.plant_panel.load_placed(data["plants"])

        for s in data.get("structures", []):
            self.map_widget.load_structure(s["struct_def"], s["lat"], s["lng"])

        for h in data.get("hedgerows", []):
            self.map_widget.load_hedgerow(h)

        for sh in data.get("shapes", []):
            self.map_widget.load_shape(sh)

        # Contour lines are loaded via JS (finishContour re-uses the drawing logic)
        # We redraw them directly as polylines
        for ctr in data.get("contours", []):
            self.map_widget.apply_loaded_contour(ctr)

        # Auto-generated contours (MultiLineString features) are restored
        # directly as a single layer group. Slope ramp PNG isn't persisted —
        # the user re-runs Generate to recompute it on demand.
        auto_contours = data.get("auto_contours") or []
        if auto_contours:
            color = auto_contours[0].get("color", "#44cc00")
            self.map_widget.draw_auto_contours(
                [{"elevation_m": c["elevation_m"], "segments": c["segments"]}
                 for c in auto_contours],
                color=color,
                show_labels=True,
            )
        if data.get("slope_overlay"):
            self.site_panel.set_auto_terrain_status(
                "Slope ramp not loaded from file — click Generate to recompute."
            )

        # Restore property pin + cached site data, if any.
        sc = proj.get("properties", {}).get("site_config") or {}
        plat, plng = sc.get("latitude"), sc.get("longitude")
        if plat is not None and plng is not None:
            label = sc.get("pin_label", "")
            self.map_widget.place_site_pin(plat, plng, label)
            has_cache = any(sc.get(k) for k in
                            ("rainfall", "soil", "elevation", "hardiness"))
            self.site_panel.set_pin(plat, plng, label, fetch=not has_cache)
            # Replay any cached results without hitting the network again.
            for key, slot in (
                ("hardiness", self.site_panel._on_hardiness),
                ("elevation", self.site_panel._on_elevation),
                ("rainfall",  self.site_panel._on_rainfall),
                ("soil",      self.site_panel._on_soil),
            ):
                if sc.get(key):
                    slot(sc[key])

        # Load notes
        notes = proj.get("properties", {}).get("notes", "")
        self.planning_panel.set_notes(notes)

        name = proj.get("properties", {}).get("project_name", "Design")
        self.setWindowTitle(f"PermaDesign — {name}")

        self._sync_planning_panel()

    def _on_save(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._on_save()

    def _on_save_as(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._on_save_as()

    def _save_to_path(self, path: str):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._save_to_path(path)

    # ── Autosave ──────────────────────────────────────────────────────────────

    def _start_autosave(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._start_autosave()

    def _autosave(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._autosave()

    # ── Plant order list export ──────────────────────────────────────────────

    # Form (seed / plug / container) inferred from plant_type. Native nurseries
    # commonly stock trees/shrubs as containers, herbaceous as plugs, and grasses
    # / forbs as seed for broadcast applications.
    _PLANT_FORM_BY_TYPE = {
        "tree":        "container",
        "shrub":       "container",
        "vine":        "container",
        "herb":        "plug or seed",
        "groundcover": "plug or seed",
        "root":        "bulb / tuber",
    }

    def _on_export_shopping_list(self):
        if not self._placed_plants:
            QMessageBox.information(self, "Plant Order List", "No plants placed yet.")
            return

        from collections import Counter
        counts: Counter = Counter()
        names: dict[int, str] = {}
        for p in self._placed_plants:
            pid = p["plant_id"]
            counts[pid] += 1
            names[pid] = p["common_name"]

        try:
            from src.db.plants import get_plant
        except Exception:
            get_plant = lambda pid: None

        # Bucket by sourcing channel:
        #   native_trees_shrubs → ALCLA / Bow Valley Habitat Development
        #   native_herbaceous   → ALCLA / Wild About Flowers / Bedrock Seed Bank
        #   cultivated          → local garden centres
        native_woody: list[tuple[str, str, str, int]] = []
        native_herb:  list[tuple[str, str, str, int]] = []
        cultivated:   list[tuple[str, str, str, int]] = []

        total = 0
        for pid, qty in counts.items():
            plant = get_plant(pid) or {}
            ptype = plant.get("plant_type", "other")
            sci   = plant.get("scientific_name", "")
            native = bool(plant.get("native_to_alberta"))
            form  = self._PLANT_FORM_BY_TYPE.get(ptype, "—")
            entry = (names[pid], sci, form, qty)
            if native and ptype in ("tree", "shrub", "vine"):
                native_woody.append(entry)
            elif native:
                native_herb.append(entry)
            else:
                cultivated.append(entry)
            total += qty

        def fmt_section(title: str, items: list[tuple[str, str, str, int]]) -> list[str]:
            if not items:
                return []
            out = [title, "-" * len(title)]
            for name, sci, form, qty in sorted(items, key=lambda x: x[0].lower()):
                line = f"  {name}"
                if sci:
                    line += f"  ({sci})"
                line += f"  ×{qty}  [{form}]"
                out.append(line)
            out.append("")
            return out

        lines = [
            "PermaDesign — Native Plant Order List",
            "=" * 44,
            "",
        ]
        lines += fmt_section(
            "NATIVE TREES & SHRUBS  (sources: ALCLA, Bow Valley Habitat)",
            native_woody,
        )
        lines += fmt_section(
            "NATIVE HERBACEOUS & GROUNDCOVER  "
            "(sources: ALCLA, Wild About Flowers, Bedrock Seed Bank)",
            native_herb,
        )
        lines += fmt_section(
            "CULTIVATED / NON-NATIVE  (sources: local garden centres)",
            cultivated,
        )

        lines.append("=" * 44)
        n_native = sum(qty for _, _, _, qty in native_woody + native_herb)
        n_cult   = sum(qty for _, _, _, qty in cultivated)
        lines.append(
            f"Total: {total} plants ({len(counts)} species)  "
            f"— {n_native} native, {n_cult} cultivated"
        )
        lines.append("")
        lines.append("Alberta native plant nurseries / seed sources:")
        lines.append("  • ALCLA Native Plants            https://alclanativeplants.com/")
        lines.append("  • Bow Valley Habitat Development https://bowvalleyhabitat.com/")
        lines.append("  • Wild About Flowers             https://wildaboutflowers.ca/")
        lines.append("  • Bedrock Seed Bank              https://bedrockseedbank.ca/")

        text = "\n".join(lines)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plant Order List", "plant_order_list.txt",
            "Text Files (*.txt);;CSV (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.statusBar().showMessage(f"Plant order list saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    # ── Undo / Redo ────────────────────────────────────────────────────────

    # ── PDF export (V3) ────────────────────────────────────────────────────

    def _on_export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF", "design.pdf",
            "PDF Files (*.pdf);;All Files (*)"
        )
        if not path:
            return
        if not path.endswith(".pdf"):
            path += ".pdf"

        try:
            from src.pdf_export import export_pdf

            # Enrich placed plants with type info for the PDF
            enriched = []
            for p in self._placed_plants:
                entry = dict(p)
                try:
                    from src.db.plants import get_plant
                    plant_data = get_plant(p["plant_id"])
                    if plant_data:
                        entry["plant_type"] = plant_data.get("plant_type", "herb")
                except Exception:
                    pass
                enriched.append(entry)

            # Capture map screenshot
            pixmap = self.map_widget.grab()

            # Gather structures from project
            structs = [
                f["properties"].get("struct_def", {})
                for f in self._project.get("features", [])
                if f.get("properties", {}).get("element_type") == "structure"
            ]

            notes = self.planning_panel.get_notes()

            export_pdf(path, self._project, enriched, structs, notes, pixmap)
            self.statusBar().showMessage(f"PDF exported: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "PDF Export Failed", str(exc))

    # ── Design notes (V4) ────────────────────────────────────────────────

    def _on_notes_changed(self, text: str):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_notes_changed(text)

    # ── Timeline / succession ──────────────────────────────────────────────

    def _on_timeline_year_changed(self, year: int):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_timeline_year_changed(year)

    # ── Planning panel sync ──────────────────────────────────────────────

    def _sync_planning_panel(self):
        """Push current placed plants and structures to planning + analysis panels."""
        enriched = []
        for p in self._placed_plants:
            entry = dict(p)
            try:
                from src.db.plants import get_plant
                plant_data = get_plant(p["plant_id"])
                if plant_data:
                    entry["plant_type"] = plant_data.get("plant_type", "herb")
                    entry["water_needs"] = plant_data.get("water_needs", "medium")
                    entry["native_to_alberta"] = bool(plant_data.get("native_to_alberta"))
            except Exception:
                pass
            enriched.append(entry)
        self.planning_panel.set_placed_plants(enriched)

        structs = []
        for f in self._project.get("features", []):
            props = f.get("properties", {})
            if props.get("element_type") == "structure":
                sd = props.get("struct_def", {})
                structs.append(sd)
        self.planning_panel.set_structures(structs)

        # Habitat Value Score tab in the analysis panel uses the same data.
        self.analysis_panel.set_placed_plants(enriched)
        self.analysis_panel.set_structures(structs)

        # Read-only shade-mix breakdown from the cached tags (if classified).
        try:
            from src.db import shade_zones
            pk = shade_zones.project_key_for(getattr(self, "_project_path", None))
            self.analysis_panel.set_shade_breakdown(shade_zones.tag_counts(pk))
        except Exception:  # noqa: BLE001
            pass

        # "On This Design" sibling inner tab. Push both: Communities + Stats
        # sub-tabs read from the enriched list; the Plants sub-tab reads
        # from `_placed_counts` (this catches load-project / new-project
        # paths where placed_counts_changed didn't fire one-for-one).
        try:
            self.on_this_design.set_plants_counts(self.plant_panel._placed_counts)
            self.on_this_design.set_design_data(enriched)
        except Exception:
            pass

    def _push_undo(self, entry: dict):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._push_undo(entry)

    def _do_undo(self):
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        action = entry["action"]

        if action == "place_plant":
            # Remove the most recent marker matching this plant + coords
            pid, lat, lng = entry["plant_id"], entry["lat"], entry["lng"]
            self.map_widget.undo_place_plant(pid, lat, lng)
            # Remove from placed list
            for i in range(len(self._placed_plants) - 1, -1, -1):
                p = self._placed_plants[i]
                if (p["plant_id"] == pid
                        and abs(p["lat"] - lat) < 1e-7
                        and abs(p["lng"] - lng) < 1e-7):
                    self._placed_plants.pop(i)
                    break
            # Remove from project features
            kept = []
            removed = False
            for f in reversed(self._project["features"]):
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (not removed
                        and props.get("element_type") == "plant"
                        and props.get("plant_id") == pid
                        and coords
                        and abs(coords[1] - lat) < 1e-7
                        and abs(coords[0] - lng) < 1e-7):
                    removed = True
                else:
                    kept.append(f)
            self._project["features"] = list(reversed(kept))
            self.plant_panel.on_plant_removed(pid)
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: removed plant", 2000)

        elif action == "place_structure":
            sid = entry["struct_id"]
            lat = entry["lat"]
            lng = entry["lng"]
            self.map_widget.undo_structure_at(sid, lat, lng)
            kept = []
            removed = False
            # Existing tree/building marks (V1.49) also undo through here.
            _undoable = {"structure", "existing_tree", "existing_building"}
            for f in reversed(self._project["features"]):
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (not removed
                        and props.get("element_type") in _undoable
                        and props.get("struct_id") == sid
                        and coords
                        and abs(coords[1] - lat) < 1e-7
                        and abs(coords[0] - lng) < 1e-7):
                    removed = True
                else:
                    kept.append(f)
            self._project["features"] = list(reversed(kept))
            self._redo_stack.append(entry)
            self.statusBar().showMessage(
                f"Undo: removed {entry.get('name', 'structure')}", 2000
            )
            self._sync_planning_panel()

        elif action == "place_boundary":
            bid = entry["boundary_id"]
            self.map_widget.undo_boundary(bid)
            self._project["features"] = [
                f for f in self._project["features"]
                if not (f.get("properties", {}).get("element_type")
                        == "property_boundary"
                        and f["properties"].get("boundary_id") == bid)
            ]
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: removed boundary", 2000)

        elif action == "place_contour":
            elev = float(entry.get("elevation_m") or 0.0)
            self.map_widget.undo_last_contour(elev)
            kept = []
            removed = False
            for f in reversed(self._project["features"]):
                props = f.get("properties", {})
                if (not removed
                        and props.get("element_type") == "contour_line"
                        and abs(float(props.get("elevation_m") or 0.0)
                                - elev) < 1e-3):
                    removed = True
                else:
                    kept.append(f)
            self._project["features"] = list(reversed(kept))
            self._redo_stack.append(entry)
            self.statusBar().showMessage(
                f"Undo: removed contour at {elev:.1f}m", 2000
            )

        elif action == "place_hedgerow":
            hid = entry["hedge_id"]
            self.map_widget.undo_hedgerow_by_id(hid)
            self._project["features"] = [
                f for f in self._project["features"]
                if f.get("properties", {}).get("hedge_id") != hid
            ]
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: removed hedgerow", 2000)

        elif action == "place_custom_shape":
            sid = entry["shape_id"]
            self.map_widget.undo_custom_shape_by_id(sid)
            self._project["features"] = [
                f for f in self._project["features"]
                if f.get("properties", {}).get("shape_id") != sid
            ]
            self._redo_stack.append(entry)
            label = entry.get("label") or entry.get("shape_type") or "shape"
            self.statusBar().showMessage(f"Undo: removed {label}", 2000)

        elif action == "move_plant":
            # Reverse a singleton drag: snap the marker (and project
            # state) back to its old lat/lng.
            pid     = entry["plant_id"]
            old_lat = float(entry["old_lat"])
            old_lng = float(entry["old_lng"])
            new_lat = float(entry["new_lat"])
            new_lng = float(entry["new_lng"])
            # Search for the marker at its post-drag position; move it
            # back to the pre-drag spot.
            self.map_widget.revert_plant_position(
                pid, new_lat, new_lng, old_lat, old_lng,
            )
            for p in self._placed_plants:
                if (p["plant_id"] == pid
                        and abs(p["lat"] - new_lat) < 1e-7
                        and abs(p["lng"] - new_lng) < 1e-7):
                    p["lat"] = old_lat
                    p["lng"] = old_lng
                    break
            for f in self._project["features"]:
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (props.get("element_type") == "plant"
                        and props.get("plant_id") == pid
                        and coords
                        and abs(coords[1] - new_lat) < 1e-7
                        and abs(coords[0] - new_lng) < 1e-7):
                    f["geometry"]["coordinates"] = [old_lng, old_lat]
                    break
            self._redo_stack.append(entry)
            self.statusBar().showMessage("Undo: plant move", 2000)

        elif action == "move_plant_group":
            originals = entry.get("originals") or []
            moved     = entry.get("moved") or []
            moved_by_id = {m.get("markerId"): m for m in moved}
            # Reverse direction in JS: snap each marker back from its
            # moved position to its original.
            for orig in originals:
                mid = orig.get("markerId")
                new = moved_by_id.get(mid)
                if not new:
                    continue
                pid = int(orig.get("plantId") or 0)
                ol  = float(orig.get("lat") or 0.0)
                og  = float(orig.get("lng") or 0.0)
                nl  = float(new.get("lat") or 0.0)
                ng  = float(new.get("lng") or 0.0)
                # Marker is currently at the post-drag (nl, ng); move it
                # back to the pre-drag (ol, og).
                self.map_widget.revert_plant_position(pid, nl, ng, ol, og)
                for p in self._placed_plants:
                    if (p["plant_id"] == pid
                            and abs(p["lat"] - nl) < 1e-7
                            and abs(p["lng"] - ng) < 1e-7):
                        p["lat"] = ol
                        p["lng"] = og
                        break
                for f in self._project["features"]:
                    props = f.get("properties", {})
                    coords = f.get("geometry", {}).get("coordinates", [])
                    if (props.get("element_type") == "plant"
                            and props.get("plant_id") == pid
                            and coords
                            and abs(coords[1] - nl) < 1e-7
                            and abs(coords[0] - ng) < 1e-7):
                        f["geometry"]["coordinates"] = [og, ol]
                        break
            self._redo_stack.append(entry)
            self.statusBar().showMessage(
                f"Undo: polyculture move ({len(originals)} plants)", 2000
            )

        self._act_undo.setEnabled(bool(self._undo_stack))
        self._act_redo.setEnabled(bool(self._redo_stack))
        self._mark_modified()

    def _do_redo(self):
        if not self._redo_stack:
            return
        entry = self._redo_stack.pop()
        action = entry["action"]

        if action == "place_plant":
            pid = entry["plant_id"]
            name = entry["common_name"]
            lat, lng = entry["lat"], entry["lng"]
            spacing_m, plant_type, custom_color = self._plant_info(pid)
            self.map_widget.load_plant_marker(
                pid, name, lat, lng, spacing_m, plant_type, custom_color
            )
            self._placed_plants.append({
                "plant_id": pid, "common_name": name, "lat": lat, "lng": lng
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "quantity": 1
                }
            })
            self.plant_panel.on_plant_placed(pid, name)
            self._undo_stack.append(entry)
            self.statusBar().showMessage("Redo: placed plant", 2000)

        self._act_undo.setEnabled(bool(self._undo_stack))
        self._act_redo.setEnabled(bool(self._redo_stack))
        self._mark_modified()

    # ── Window close ─────────────────────────────────────────────────────────

    # ── LOAD-BEARING RESIZE HANDLERS ─────────────────────────────────────
    # Both event handlers below are critical infrastructure for the map
    # resize / maximise behaviour on Windows. See the matching block
    # comment in src/map_widget.py above MapWidget.invalidate_size for
    # the full story. Short version: the _dbg() file I/O inside these
    # handlers and the singleShot(0) invalidate in changeEvent together
    # give Chromium's renderer enough scheduling slack to commit its new
    # viewport before Leaflet measures the container. Don't trim them.
    # ─────────────────────────────────────────────────────────────────────

    def changeEvent(self, event):
        # Qt fires WindowStateChange on F11/maximise/restore. The embedded
        # QWebEngineView doesn't always get its own resizeEvent in the same
        # frame, so Leaflet's canvas renderer can cache a stale 0x0 size and
        # paint into nothing. Posting invalidate_size on the next event-loop
        # tick lets Qt finish the state transition first.
        if event.type() == QEvent.Type.WindowStateChange:
            try:
                # _dbg() is load-bearing here, not diagnostic: the file
                # write yields to the OS scheduler and lets Chromium
                # propagate the new viewport before invalidate_size runs.
                from src.map_widget import _dbg
                _dbg(f"[mainwindow] WindowStateChange state={int(self.windowState())} "
                     f"size={self.width()}x{self.height()}")
            except Exception:
                pass
            QTimer.singleShot(0, self.map_widget.invalidate_size)
        super().changeEvent(event)

    def resizeEvent(self, event):
        # The override exists for the same load-bearing reason as the
        # _dbg() call inside: the Python frame + file syscall together
        # introduce just enough scheduling delay for Chromium's IPC to
        # land between Qt's resize and super().resizeEvent propagating
        # the new size down to MapWidget. Removing the override (or just
        # the _dbg call) reintroduces the half-painted-map symptom on
        # Windows after a maximise with LiDAR contours visible.
        try:
            from src.map_widget import _dbg
            sz = event.size()
            _dbg(f"[mainwindow] resizeEvent w={sz.width()} h={sz.height()} "
                 f"state={int(self.windowState())}")
        except Exception:
            pass
        super().resizeEvent(event)

    def closeEvent(self, event):
        if self._modified:
            r = QMessageBox.question(
                self, "Exit",
                "You have unsaved changes. Exit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel_draw()
            self.map_widget.clear_selection()
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            # Delete every currently-selected map item (across types).
            self.map_widget.delete_selected()
        elif key == Qt.Key.Key_B and not event.modifiers():
            self._enter_boundary_mode()
        elif key == Qt.Key.Key_P and not event.modifiers():
            # Switch to Plants tab
            self._side_tabs.setCurrentWidget(self.plant_panel)
        elif key == Qt.Key.Key_G and not event.modifiers():
            # Switch to Polycultures tab
            self._side_tabs.setCurrentWidget(self.polyculture_panel)
        elif key == Qt.Key.Key_S and not event.modifiers():
            # Switch to Structures tab
            self._side_tabs.setCurrentWidget(self.structure_panel)
        elif key == Qt.Key.Key_A and not event.modifiers():
            # Switch to Analysis tab
            self._side_tabs.setCurrentWidget(self.analysis_panel)
        elif key == Qt.Key.Key_T and not event.modifiers():
            # Switch to Planning tab
            self._side_tabs.setCurrentWidget(self.planning_panel)
        elif key == Qt.Key.Key_M and not event.modifiers():
            self._enter_measure_mode()
        elif key == Qt.Key.Key_N and not event.modifiers():
            self._enter_annotate_mode()
        elif key == Qt.Key.Key_L and not event.modifiers():
            # Toggle map legend
            self.map_widget.toggle_legend()
        else:
            super().keyPressEvent(event)

    def _clear_undo(self):
        """Clear undo/redo stacks (e.g. on New/Open project)."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._act_undo.setEnabled(False)
        self._act_redo.setEnabled(False)


# ── Helper widgets ────────────────────────────────────────────────────────────

def _fmt_time(decimal_hour: float) -> str:
    """Format a decimal hour (e.g. 6.5) as '6:30 AM'."""
    h = int(decimal_hour)
    m = int((decimal_hour - h) * 60)
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"


def _vsep() -> QWidget:
    """Thin vertical separator widget for the status bar."""
    w = QWidget()
    w.setFixedWidth(1)
    w.setStyleSheet("background: #37474f;")
    return w


# ── Application-wide stylesheet ───────────────────────────────────────────────

_APP_STYLE = """
QMainWindow, QWidget {
    background-color: #1a2a1a;
    color: #c8e6c9;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}

QMenuBar {
    background-color: #1b2b1b;
    color: #c8e6c9;
    border-bottom: 1px solid #2e4a2e;
}
QMenuBar::item:selected {
    background-color: #2e4a2e;
}
QMenu {
    background-color: #1e2e1e;
    color: #c8e6c9;
    border: 1px solid #2e4a2e;
}
QMenu::item:selected {
    background-color: #2e4a2e;
}

QToolBar {
    background-color: #1b2b1b;
    border-bottom: 1px solid #2e4a2e;
    spacing: 4px;
    padding: 2px 4px;
}
QToolButton {
    color: #c8e6c9;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 3px 8px;
}
QToolButton:hover {
    background: #2e4a2e;
    border-color: #4a7a4a;
}
QToolButton:checked {
    background: #2e5a2e;
    border-color: #66bb6a;
    color: #a5d6a7;
}

QStatusBar {
    background-color: #152015;
    color: #78909c;
    border-top: 1px solid #2e4a2e;
    font-size: 12px;
}

QSplitter::handle {
    background-color: #2e4a2e;
    width: 2px;
}

QScrollBar:vertical {
    background: #1a2a1a;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #2e4a2e;
    border-radius: 5px;
}
"""
