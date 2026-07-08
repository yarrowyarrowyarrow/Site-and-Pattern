"""
app.py — Main application window for Site & Pattern.

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
from src.climate          import zone_label
from src.collapsible_panel import CollapsibleSidebar
import src.project as project_io
from src.controllers.update_flow import UpdateFlowController
from src.controllers.mode import ModeController
from src.controllers.persistence import PersistenceController
from src.controllers.map_events import MapEventRouter
from src.controllers.generation import GenerationController
from src.controllers.area_fill_controller import AreaFillController
from src.project_store import ProjectStore
from src.scan_import_dialog import start_scan_import as _start_scan_import
from src.scene3d_window import open_3d_view as _open_3d_view
from src.reference_ecosystem_window import (
    open_reference_ecosystem as _open_reference_ecosystem)
from src.snapshot_window import open_snapshot_view as _open_snapshot_view
from src.sprite_gallery_window import open_sprite_gallery as _open_sprite_gallery
from src.branding import APP_NAME, APP_TITLE


# Marker colour tables for plant-community members — moved to the Qt-free
# src.member_colors so placement controllers can colour members without
# importing this (QtWebEngine-bound) module. Re-exported under the old names
# for existing importers.
from src.member_colors import (
    LAYER_COLORS as _LAYER_COLORS,
    FUNCTION_COLORS as _FUNCTION_COLORS,
    OTHER_COLOR as _OTHER_COLOR,
    member_color as _member_color,
)


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

    # Placed-plant state lives in the ProjectStore (the single write path —
    # src/project_store.py); these delegate so the ~100 existing read sites
    # keep working unchanged. Defined via property() rather than @property
    # so the architecture guard's MainWindow method count stays a measure
    # of behaviour, not accessors.
    _project = property(
        lambda self: self._store.project,
        lambda self, v: self._store.set_project(v))
    _placed_plants = property(
        lambda self: self._store.placed_plants,
        lambda self, v: self._store.replace_placed_plants(v))

    def __init__(self):
        super().__init__()
        _init_database()
        self.setWindowTitle(APP_TITLE)
        self.resize(1400, 860)
        self.setMinimumSize(900, 600)

        # Project state. The ProjectStore owns the project dict AND the
        # placed-plants index, and is the only supported write path for
        # placed-plant state (see src/project_store.py). _project /
        # _placed_plants are delegating properties on the class below.
        self._store        = ProjectStore(project_io.new_project())
        self._project_path = None        # path when saved to file
        self._modified     = False
        self._current_zone = None
        self._current_mode = 'none'

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
        self._area_fill = AreaFillController(self)
        # Pending draw-then-fill spec (F3): {members, spacing, name} set when a
        # Fill Area button is clicked; consumed when the user finishes the polygon.
        self._pending_fill = None

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

        from src.fill_tab_widget import FillTabWidget
        self._side_tabs = FillTabWidget()
        # Document mode lets the tab bar span the full width, which is what lets
        # FillTabWidget stretch the tabs edge-to-edge (no gap after "Planning").
        self._side_tabs.setDocumentMode(True)
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
        # Show every label in full, and stretch the tabs to fill the whole tab
        # strip (no empty gap to the right of "Planning").
        self._side_tabs.tabBar().setUsesScrollButtons(False)
        self._side_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self._side_tabs.tabBar().setExpanding(True)
        # Tab styling — every tab strip in the app (these top-level tabs plus
        # the Site/Plants/Analysis/Planning sub-tabs) shares the same
        # green-underline look so the whole UI is consistent. A subtle pane
        # border frames the side panel.
        from src.ui_style import inner_tab_stylesheet
        self._side_tabs.setStyleSheet(
            inner_tab_stylesheet()
            + "QTabWidget::pane { border: 1px solid #2e4a2e; top: -1px; }"
            # Tighter horizontal padding than the sub-tabs so all five top-level
            # labels still render in full at the 260px minimum panel width.
            + "QTabBar::tab { padding: 5px 8px; }"
            + "QWidget { background-color: #1e2a1e; color: #c8e6c9; }"
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
        from src.fill_tab_widget import FillTabWidget
        inner = FillTabWidget(wrap)
        inner.setDocumentMode(True)
        inner.tabBar().setUsesScrollButtons(False)
        inner.tabBar().setExpanding(True)
        inner.setStyleSheet(inner_tab_stylesheet())
        inner.addTab(self.plant_panel, "Plants")
        inner.addTab(self.polyculture_panel, "Plant Communities")
        inner.addTab(self.on_this_design, "On This Design")
        v.addWidget(inner)
        # Kept for programmatic tab jumps (Site tab's ecoregion → community
        # library cross-link, V2.13).
        self._plants_inner_tabs = inner
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

        act_scan = file_menu.addAction("Import &Yard Scan…")
        act_scan.setStatusTip(
            "Import a phone scan (Polycam/Scaniverse PLY, XYZ, LAS) — "
            "match 2+ points to the map and the scanned structures cast "
            "shade and appear in 3D")
        # Lambda, not a MainWindow method — the flow lives in
        # src/scan_import_dialog.py (architecture-guard method ceiling).
        act_scan.triggered.connect(lambda: _start_scan_import(self))

        file_menu.addSeparator()

        act_shopping = file_menu.addAction("Export Planting &Plan…")
        act_shopping.setStatusTip(
            "Export a buy-it / plant-it planting plan — quantities, cost, spacing, "
            "and a phased planting schedule, grouped by Alberta nursery source")
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
        act_3d = view_menu.addAction("&3D Preview…")
        act_3d.setStatusTip(
            "Open the 3D view of this design — growth timeline, sun "
            "shadows, terrain"
        )
        # Lambda (not a MainWindow method) on purpose: the window manages
        # itself in src/scene3d_window.py and the architecture guard's
        # method ceiling stays meaningful.
        act_3d.triggered.connect(lambda: _open_3d_view(self))

        act_reference = view_menu.addAction("Walk a &Reference Ecosystem…")
        act_reference.setStatusTip(
            "Walk the natural community your ecoregion is reaching toward — "
            "the reference target for this design (F50)"
        )
        # Lambda (not a MainWindow method): the window lives in
        # src/reference_ecosystem_window.py, off MainWindow's method ledger.
        act_reference.triggered.connect(
            lambda: _open_reference_ecosystem(self))

        act_snapshots = view_menu.addAction("&Growth Snapshots…")
        act_snapshots.setStatusTip(
            "See this design at years 1 / 5 / 15 / 30 side by side — watch "
            "the plants grow and fill in over time"
        )
        # Lambda for the same reason as 3D Preview: the window lives in
        # src/snapshot_window.py, off MainWindow's method ledger.
        act_snapshots.triggered.connect(lambda: _open_snapshot_view(self))

        act_gallery = view_menu.addAction("3D &Sprite Gallery…")
        act_gallery.setStatusTip(
            "Browse every 3D plant archetype + flower sprite — compare species "
            "(spruce vs pine vs fir, etc.) and pick a detail level"
        )
        # Lambda for the same reason: the window self-manages in
        # src/sprite_gallery_window.py, off MainWindow's method ledger.
        act_gallery.triggered.connect(lambda: _open_sprite_gallery(self))

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
        from src.app_version import build_version
        # Frozen builds have no git; the version is baked in at build time.
        current_branch = build_version() or self._current_branch_name() or ""
        version_disp = current_branch if parse_version_branch(current_branch) else "dev"
        act_about = help_menu.addAction(f"&About / Version: {version_disp}")
        act_about.setStatusTip(
            "Show the current Site & Pattern version, schema version, and "
            "git commit hash"
        )
        act_about.triggered.connect(self._on_about)

        act_update = help_menu.addAction("Check for &Updates…")
        act_update.setStatusTip("Get the latest version: pulls via git on source "
                                "installs, or downloads and installs the newest "
                                "release in-app on packaged (.dmg/.exe) installs")
        act_update.triggered.connect(self._on_check_for_updates)

        act_pick = help_menu.addAction("&Switch to a specific version…")
        act_pick.setStatusTip(
            "Pick any published V<major>.<minor> version. Source installs "
            "check out that branch; packaged installs download and install "
            "that version's installer."
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
        b.selection_moved.connect(self._on_selection_moved)
        b.fill_area_complete.connect(self._on_fill_area_complete)
        b.map_ready.connect(self._on_map_ready)

        # Toolbar → map
        self.toolbar.draw_boundary_requested.connect(self._enter_boundary_mode)
        self.toolbar.measure_requested.connect(self._enter_measure_mode)
        self.toolbar.annotate_requested.connect(self._enter_annotate_mode)
        self.toolbar.select_requested.connect(self._enter_select_mode)
        self.toolbar.cancel_draw_requested.connect(self._cancel_draw)
        self.toolbar.undo_requested.connect(self._do_undo)
        self.toolbar.redo_requested.connect(self._do_redo)

        self.toolbar.satellite_toggled.connect(self.map_widget.set_satellite_visible)
        self.toolbar.boundary_toggled.connect(self.map_widget.set_boundary_visible)
        self.toolbar.measurements_toggled.connect(
            self.map_widget.set_measurements_visible
        )
        self.toolbar.plants_toggled.connect(self.map_widget.set_plants_visible)
        self.toolbar.canopy_toggled.connect(self.map_widget.set_canopy_visible)
        self.toolbar.yard_photo_toggled.connect(
            self.map_widget.set_splat_ortho_visible)
        self.toolbar.grid_settings_changed.connect(self._on_grid_settings_changed)

        # Plant panel → map (plant placement + colour). Pattern mode info
        # arrives in the 4th argument; legacy single-mode placements pass
        # {"kind": "single"}.
        self.plant_panel.place_plant_requested.connect(self._enter_plant_mode)
        self.plant_panel.color_changed.connect(self._on_plant_color_changed)

        # Map → remove plant marker
        b.plant_removed.connect(self._on_plant_removed)
        b.plants_removed_batch.connect(self._on_plants_removed_batch)

        # Map → batch placement (Burst, Row, Grid, Circle)
        b.pattern_placed.connect(self._on_pattern_placed)

        # Map → annotations
        b.annotate_requested.connect(self._on_annotate_requested)
        b.annotation_removed.connect(self._on_annotation_removed)

        # Polyculture panel → map (polyculture placement)
        self.polyculture_panel.placePolycultureRequested.connect(self._enter_polyculture_mode)
        self.polyculture_panel.fillAreaRequested.connect(self._on_community_fill_requested)
        self.polyculture_panel.fillCommunityMixRequested.connect(self._on_community_mix_fill_requested)
        self.plant_panel.fill_area_requested.connect(self._on_plants_fill_requested)
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
        # Clears routed through the controller so they reset the active-overlay
        # state and record an undo step (not straight to the map widget).
        self.analysis_panel.sun_path_cleared.connect(
            self._map_events._on_sun_path_removed)
        self.analysis_panel.sector_requested.connect(self._on_sector_requested)
        self.analysis_panel.sector_cleared.connect(
            self._map_events._on_sectors_cleared)
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
        # Straight to the controller (MainWindow at its method ceiling).
        self.site_panel.download_soil_requested.connect(
            self._map_events._on_download_soil_requested)
        # Shade overlay + OSM import (V1.51).
        self.site_panel.shade_requested.connect(self._on_shade_requested)
        self.site_panel.shade_cleared.connect(self._on_shade_cleared)
        self.site_panel.shade_opacity.connect(self._on_shade_opacity)
        self.site_panel.shade_zones_requested.connect(self._on_shade_zones_requested)
        self.site_panel.shade_zones_visible_changed.connect(
            self.map_widget.set_shade_zones_visible)
        self.site_panel.osm_import_requested.connect(self._on_osm_import_requested)
        # Wired straight to the controller (MainWindow is at its method ceiling,
        # so no shim) — the building-pack download lives in MapEventRouter.
        self.site_panel.download_buildings_requested.connect(
            self._map_events._on_download_buildings_requested)
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

        # Site-walk field notes (F6) — store on the project + mark modified.
        # Two thin lambdas (MainWindow is at its method ceiling).
        from src import field_notes as _field_notes
        self.site_panel.field_notes_changed.connect(
            lambda notes: _field_notes.set_field_notes(self._project, notes))
        self.site_panel.field_notes_changed.connect(
            lambda _notes: self._mark_modified())

        # Site photo overlay (F24) — wired straight to the flow module (free
        # functions taking ``main``, mirroring splat_flow; MainWindow is full).
        from src import site_photo_flow
        self.site_panel.site_photo_import_requested.connect(
            lambda path: site_photo_flow.import_site_photo(self, path))
        self.site_panel.site_photo_width_changed.connect(
            lambda w: site_photo_flow.set_width(self, w))
        self.site_panel.site_photo_opacity_changed.connect(
            lambda o: site_photo_flow.set_opacity(self, o))
        self.site_panel.site_photo_visible_changed.connect(
            lambda v: self.map_widget.set_site_photo_visible(v))
        self.site_panel.site_photo_clear_requested.connect(
            lambda: site_photo_flow.clear_site_photo(self))

        self.analysis_panel.wind_requested.connect(self._on_wind_requested)
        self.analysis_panel.wind_cleared.connect(self.map_widget.clear_wind_overlay)
        # Straight to the controller (MainWindow is at its method ceiling).
        self.analysis_panel.wind_data_requested.connect(
            self._map_events._on_fetch_wind_requested)
        # Live wind shadow (V1.68) — wired straight to the flow module (both
        # MainWindow and the map-events controller are at their guard ceilings).
        from src import wind_shadow_flow
        # Toggle + committed-angle go through checkpointed controller handlers
        # so they're undoable; the live scrub stays a direct (non-undoable) call.
        self.analysis_panel.wind_shadow_toggled.connect(
            self._map_events._on_wind_shadow_toggled)
        self.analysis_panel.wind_angle_changed_live.connect(
            lambda d: wind_shadow_flow.on_angle_live(self, d))
        self.analysis_panel.wind_shadow_commit.connect(
            self._map_events._on_wind_angle_commit)
        # Snow-catch overlay (Step 3) — winter drifts in the lee of windbreaks;
        # straight to the flow module (MainWindow is at its method ceiling).
        from src import snow_microsite_flow
        self.analysis_panel.snow_catch_toggled.connect(
            lambda on: snow_microsite_flow.enable(self, on))
        # Extra slot on the existing plant-move signals → rebuild the shelter +
        # the snow-catch zones (both depend on where the sheltering plants are).
        b.plant_moved.connect(lambda *a: wind_shadow_flow.on_plants_changed(self))
        b.plant_group_moved.connect(
            lambda *a: wind_shadow_flow.on_plants_changed(self))
        b.selection_moved.connect(
            lambda *a: wind_shadow_flow.on_plants_changed(self))
        b.plant_moved.connect(lambda *a: snow_microsite_flow.on_plants_changed(self))
        b.plant_group_moved.connect(
            lambda *a: snow_microsite_flow.on_plants_changed(self))
        b.selection_moved.connect(
            lambda *a: snow_microsite_flow.on_plants_changed(self))
        self.analysis_panel.season_changed.connect(self._on_season_changed)
        # "What the bee sees" (F37): the Bees tab drives the map recolour direct
        # (payload is built panel-side, so no new MainWindow method is needed).
        self.analysis_panel.bee_map_overlay_requested.connect(
            self.map_widget.set_bee_forage_view)
        self.analysis_panel.bee_map_overlay_cleared.connect(
            self.map_widget.clear_bee_forage_view)

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
        # A dropped pin's auto-detected ecoregion drives the plant library's
        # "Restoring toward…" filter live, for this session only (V1.87).
        self.site_panel.ecoregion_detected.connect(
            self.plant_panel.set_autodetected_ecoregion)
        # "Browse N reference communities →" jumps to the community library
        # with the Habitat filter pre-set to the detected ecoregion (V2.13).
        # Handlers live in design_review_flow (MainWindow is at its method
        # ceiling), wired through thin lambdas.
        from src import design_review_flow as _drf
        self.site_panel.browse_communities_requested.connect(
            lambda key: _drf.browse_communities(self, key))
        # On This Design rows → map (V2.13): click to locate, context menu to
        # select / remove / open in the Plant Library.
        self.on_this_design.species_focus_requested.connect(
            lambda pid: _drf.focus_species(self, pid))
        self.on_this_design.species_select_requested.connect(
            lambda pid: _drf.select_species(self, pid))
        self.on_this_design.species_remove_requested.connect(
            lambda pid: _drf.remove_species(self, pid))
        self.on_this_design.species_show_in_library_requested.connect(
            lambda pid: _drf.show_in_library(self, pid))
        self.on_this_design.community_focus_requested.connect(
            lambda name: _drf.focus_community(self, name))
        # Stats deep-links: habitat value → Analysis, cost → Planning (V2.13).
        self.on_this_design.open_habitat_analysis_requested.connect(
            lambda: _drf.open_habitat_analysis(self))
        self.on_this_design.open_planning_requested.connect(
            lambda: _drf.open_planning(self))
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

    def _enter_select_mode(self):
        # Shim → ModeController; see src/controllers/mode.py.
        return self._mode._enter_select_mode()

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
        # Remember the rendered overlay so undo/redo can reproduce it.
        self._active_sun_state = (config, lat, lng)

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

    # ── Draw-then-fill plant placement (F3) ──────────────────────────────────

    def _start_fill(self, members, spacing_m, name, matrix=False):
        """Arm a draw-then-fill: stash the spec, then enter the map 'fill' mode so
        the user draws the polygon to scatter ``members`` (each ``(plant_id,
        weight)``) inside. Shared by the Plants tab (single plant / current mix)
        and the Plant Communities tab. ``matrix`` requests matrix planting (F22)."""
        members = [(int(pid), float(w)) for pid, w in (members or [])
                   if pid is not None]
        if not members:
            QMessageBox.information(
                self, "Fill Area",
                "Pick a plant, build a mix, or select a community first, then "
                "click Fill Area and draw the area to plant.")
            return
        self._pending_fill = {"members": members,
                              "spacing": float(spacing_m or 4.0),
                              "name": name or "",
                              "matrix": bool(matrix)}
        self._mode._enter_fill_mode()

    def _on_plants_fill_requested(self, members, spacing_m, name, matrix=False):
        """Plants tab → fill an area with the current mix or selected plant."""
        self._start_fill(members, spacing_m, name, matrix)

    def _on_community_fill_requested(self, poly_id: int, spacing_m: float,
                                     matrix=False):
        """Plant Communities tab → fill an area with whole community UNITS (each
        anchor expands the members at their designed offsets), not a scatter of
        the individual member plants."""
        from src.db.polycultures import get_polyculture_by_id
        pc = get_polyculture_by_id(int(poly_id)) or {}
        if not pc.get("members"):
            QMessageBox.information(self, "Fill Area",
                                    "That community has no members to place.")
            return
        self._pending_fill = {"kind": "community", "polyculture": pc,
                              "spacing": float(spacing_m or 0.0),
                              "matrix": bool(matrix)}
        self._mode._enter_fill_mode()

    def _on_community_mix_fill_requested(self, communities, spacing_m: float,
                                         matrix=False):
        """Plant Communities tab → fill an area from a community MIX. By default
        whole community units are scattered evenly by weight; with ``matrix`` the
        whole mix dissolves into one matrix planting (all members pooled)."""
        communities = list(communities or [])
        if len(communities) < 2:
            return
        self._pending_fill = {"kind": "community_mix", "communities": communities,
                              "spacing": float(spacing_m or 0.0),
                              "matrix": bool(matrix)}
        self._mode._enter_fill_mode()

    def _on_fill_area_complete(self, points_json: str):
        """User finished drawing the fill polygon — scatter the pending plants in
        it via AreaFillController (markers only; no hardscape shape)."""
        spec, self._pending_fill = self._pending_fill, None
        if not spec:
            return
        import json as _json
        try:
            pts = _json.loads(points_json or "[]")
        except Exception:
            return
        if len(pts) < 3:
            return
        # JS sends [lat, lng] pairs; area_fill rings are [lng, lat] (GeoJSON).
        ring = [[p[1], p[0]] for p in pts]
        kind = spec.get("kind")
        matrix = bool(spec.get("matrix"))
        if kind == "community":
            n = self._area_fill.fill_communities(ring, spec["polyculture"],
                                                 spec["spacing"], matrix=matrix)
            what = "communities"
        elif kind == "community_mix":
            n = self._area_fill.fill_community_mix(ring, spec["communities"],
                                                   spec["spacing"], matrix=matrix)
            what = "community units"
        else:
            n = self._area_fill.fill(ring, spec["members"], spec["spacing"],
                                     poly_name=spec["name"], matrix=matrix)
            what = "plants"
        if n == 0:
            QMessageBox.information(
                self, "Fill Area",
                f"No room to place {what} in that area at this spacing — try a "
                "smaller spacing or a larger area.")

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
        # Enter the dedicated JS 'polyculture' mode: it sets the crosshair and
        # clears any still-armed "Mark tree" structure mode (so a community
        # click doesn't ALSO drop a tree), while being a real placement mode —
        # NOT 'none' — so a click on a visible boundary/shape forwards to
        # onMapClick → bridge map_clicked → _on_polyculture_click.
        self.map_widget.set_mode('polyculture')
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

    def _on_selection_moved(self, originals_json: str, moved_json: str):
        return self._map_events._on_selection_moved(originals_json, moved_json)

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

    def _on_plants_removed_batch(self, batch_json: str):
        # Shim → MapEventRouter; see src/controllers/map_events.py.
        return self._map_events._on_plants_removed_batch(batch_json)

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

        # Assigning _project routes through ProjectStore.set_project, which
        # also resets the placed-plants index.
        self._project      = project_io.new_project(name)
        self._project_path = None
        self._modified     = False
        self._clear_undo()
        self._current_zone = None
        self._sb_zone.setText("Zone: —")
        self.map_widget.clear_all()
        self.map_widget.clear_site_pin()
        self.site_panel.clear_pin()
        self.plant_panel.clear_placed()
        self.plant_panel.set_zone(None)
        self.plant_panel.set_autodetected_ecoregion("")   # drop the pin's region
        self.planning_panel.set_notes("")
        self.planning_panel.set_placed_plants([])
        self.planning_panel.set_structures([])
        self.analysis_panel.set_placed_plants([])
        self.analysis_panel.set_structures([])
        # Reset site-walk field notes (F6) and clear any site photo (F24).
        self.site_panel.set_field_notes({})
        from src import site_photo_flow
        site_photo_flow.restore_site_photo(self)
        self.setWindowTitle(f"{APP_NAME} — {name}")
        self._set_mode_label("Ready")

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Design", "",
            "Site & Pattern Files (*.perma.geojson);;GeoJSON (*.geojson);;All files (*)"
        )
        if not path:
            return
        try:
            self._load_from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _load_from_path(self, path: str):
        proj = project_io.load_project(path)
        self._project      = proj   # → ProjectStore.set_project (index rebuilt)
        self._project_path = path
        self._modified     = False
        self._clear_undo()

        # Redraw the whole map from the project's features (boundaries,
        # plants, structures, hedgerows, shapes, contours, annotations,
        # auto-terrain, site pin, splat backdrop). Shared with undo/redo's
        # snapshot restore — see PersistenceController.render_project_to_map.
        self._persistence.render_project_to_map(fit_view=True)

        # Replay the panel's cached site data (the map pin itself is placed by
        # the re-render above). No network hit when the cache is present.
        sc = proj.get("properties", {}).get("site_config") or {}
        plat, plng = sc.get("latitude"), sc.get("longitude")
        if plat is not None and plng is not None:
            label = sc.get("pin_label", "")
            has_cache = any(sc.get(k) for k in
                            ("rainfall", "soil", "elevation", "hardiness"))
            self.site_panel.set_pin(plat, plng, label, fetch=not has_cache)
            for key, slot in (
                ("hardiness", self.site_panel._on_hardiness),
                ("elevation", self.site_panel._on_elevation),
                ("rainfall",  self.site_panel._on_rainfall),
                ("soil",      self.site_panel._on_soil),
                ("winter",    self.site_panel._on_winter),
            ):
                if sc.get(key):
                    slot(sc[key])
            # Restore the soil-pH plant-matching constraint from cached site data.
            if sc.get("soil_ph") is not None:
                self.plant_panel.set_soil_ph(sc.get("soil_ph"))

        # Load notes
        notes = proj.get("properties", {}).get("notes", "")
        self.planning_panel.set_notes(notes)

        # Site-walk field notes (F6). The site photo overlay (F24) is already
        # restored by render_project_to_map above (shared with undo/redo).
        from src import field_notes as _field_notes
        self.site_panel.set_field_notes(_field_notes.get_field_notes(proj))

        name = proj.get("properties", {}).get("project_name", "Design")
        self.setWindowTitle(f"{APP_NAME} — {name}")

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

    # ── Planting plan export ─────────────────────────────────────────────────

    def _on_export_shopping_list(self):
        """Export the design as a buy-it / plant-it Planting Plan (F40).

        All the assembly lives in the Qt-free :mod:`src.planting_plan` so it can
        be unit-tested and shared with the PDF export; this is just the file
        plumbing."""
        if not self._placed_plants:
            QMessageBox.information(self, "Planting Plan", "No plants placed yet.")
            return

        from src.planting_plan import build_planting_plan, render_plan_text

        structs = [
            f["properties"]["struct_def"]
            for f in self._project.get("features", [])
            if f.get("properties", {}).get("element_type") == "structure"
            and f.get("properties", {}).get("struct_def")
        ]
        bed_area = sum(
            float(f.get("properties", {}).get("area_m2") or 0.0)
            for f in self._project.get("features", [])
            if f.get("properties", {}).get("element_type") == "custom_shape"
        )
        plan = build_planting_plan(self._placed_plants, structures=structs,
                                   bed_area_m2=bed_area)
        text = render_plan_text(plan)

        # Year-by-year conversion schedule (F17): remove-this / plant-that, when.
        try:
            from src.conversion_plan import (
                build_conversion_schedule, render_schedule_text)
            from src.lawn_zones import conversion_summary
            schedule = build_conversion_schedule(
                self._placed_plants,
                summary=conversion_summary(self._project.get("features", [])),
            )
            text += "\n\n" + render_schedule_text(schedule)
        except Exception:  # noqa: BLE001 — the schedule augments the plan, never blocks it
            pass

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Planting Plan", "planting_plan.txt",
            "Text Files (*.txt);;CSV (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.statusBar().showMessage(f"Planting plan saved: {path}", 3000)
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
        # Shade-tab caster inventory (V2.13) — cheap feature scan, and this
        # sync already runs on every design mutation, project load, and after
        # OSM imports/feature marks.
        self.site_panel.update_caster_summary(self._project)
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
            # Whole-design cost (C1): plants + structure install + bed mulch,
            # with the plant total broken down by type (F2).
            from src.sourcing import design_cost, cost_by_type
            bed_area = sum(
                float(f.get("properties", {}).get("area_m2") or 0.0)
                for f in self._project.get("features", [])
                if f.get("properties", {}).get("element_type") == "custom_shape"
            )
            _cost = design_cost(enriched, structures=structs, mulch_area_m2=bed_area)
            _cost["type_costs"] = cost_by_type(enriched)
            self.on_this_design.set_cost_breakdown(_cost)
            # Lawn-to-habitat conversion tally (N2).
            from src.lawn_zones import conversion_summary
            _conv = conversion_summary(self._project.get("features", []))
            self.on_this_design.set_lawn_conversion(_conv)
            # Same summary grounds the Habitat tab's lawn-equivalent
            # counterfactual (F10) and the phased conversion plan (F17).
            self.analysis_panel.set_lawn_conversion(_conv)
            # Year-by-year conversion schedule (F17) in the planning Timeline tab.
            try:
                from src.conversion_plan import build_conversion_schedule
                self.planning_panel.set_conversion_schedule(
                    build_conversion_schedule(enriched, summary=_conv)
                )
            except Exception:  # noqa: BLE001 — schedule is a planning aid
                self.planning_panel.set_conversion_schedule(None)
            # Habitat value on the Stats tab (F11) — what the design is worth,
            # shown beside the cost. Computed here so it stays live with edits.
            try:
                from src.habitat_score import compute_habitat_score
                self.on_this_design.set_habitat_value(
                    compute_habitat_score(enriched, structs)
                )
            except Exception:  # noqa: BLE001 — value is a nicety, never break sync
                self.on_this_design.set_habitat_value(None)
        except Exception:
            pass

    def _push_undo(self, entry: dict):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._push_undo(entry)

    def _do_undo(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._do_undo()

    def _do_redo(self):
        # Shim → PersistenceController; see src/controllers/persistence.py.
        return self._persistence._do_redo()

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
        self._persistence._sync_undo_actions()


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
