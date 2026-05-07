"""
toolbar.py — Top toolbars for drawing tools, layer toggles, and project actions.

Layout (two stacked rows):

  ┌────────────────────────────────────────────────────────────────┐
  │ Draw:   ⬡ Boundary  ◎ Zone Circles  📏 Measure  📝 Note  ⤺ Undo  ✕ Cancel │
  ├────────────────────────────────────────────────────────────────┤
  │ Layers: 🛰 Satellite ⬡ Boundary ◎ Zones ✿ Plants Aa Labels …   │
  │         …  ⚙ Settings  🔍 Zoom: [Fine ▼]                        │
  └────────────────────────────────────────────────────────────────┘

`MainToolbar` is the Draw row (a QToolBar so existing
`addToolBar(self.toolbar)` calls keep working). The Layers row is held
as a separate QToolBar attribute and added via `attach_to(window)`.
"""

from PyQt6.QtWidgets import QToolBar, QLabel, QComboBox
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtCore import pyqtSignal, Qt


class MainToolbar(QToolBar):
    """The Draw toolbar (top row).

    Holds a sibling `layers_bar` QToolBar exposed for the main window to
    add on a second row. All signals — Draw, Layers, Settings, Zoom —
    live on this object so app.py wiring stays a single connection
    surface.
    """

    # Drawing mode signals
    draw_boundary_requested   = pyqtSignal()
    draw_zone_requested       = pyqtSignal()
    measure_requested         = pyqtSignal()
    annotate_requested        = pyqtSignal()
    cancel_draw_requested     = pyqtSignal()
    undo_requested            = pyqtSignal()

    # Layer visibility signals
    satellite_toggled    = pyqtSignal(bool)
    boundary_toggled     = pyqtSignal(bool)
    zones_toggled        = pyqtSignal(bool)
    plants_toggled       = pyqtSignal(bool)
    labels_toggled       = pyqtSignal(bool)
    canopy_toggled       = pyqtSignal(bool)
    snap_toggled         = pyqtSignal(bool)
    structures_toggled   = pyqtSignal(bool)
    measure_cleared      = pyqtSignal()      # "clear measure" action

    # Settings
    settings_requested = pyqtSignal()

    # Zoom sensitivity changed ('fine'|'normal'|'fast'|'coarse')
    zoom_step_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Draw", parent)
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Sibling layers toolbar — attached on a second row via attach_to().
        self.layers_bar = QToolBar("Layers", parent)
        self.layers_bar.setMovable(False)
        self.layers_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self._build_draw()
        self._build_layers()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_draw(self):
        self.addWidget(QLabel("  Draw: "))

        self._act_boundary = QAction("⬡ Boundary", self)
        self._act_boundary.setCheckable(True)
        self._act_boundary.setStatusTip("Draw property boundary polygon")
        self._act_boundary.setToolTip("Click to add points; click first point (or double-click) to close")
        self._act_boundary.triggered.connect(self._on_boundary_toggled)
        self.addAction(self._act_boundary)

        self._act_zone = QAction("◎ Zone Circles", self)
        self._act_zone.setCheckable(True)
        self._act_zone.setStatusTip("Click to place permaculture zone rings")
        self._act_zone.triggered.connect(self._on_zone_toggled)
        self.addAction(self._act_zone)

        self._act_measure = QAction("📏 Measure", self)
        self._act_measure.setCheckable(True)
        self._act_measure.setStatusTip("Click two points to measure distance")
        self._act_measure.setToolTip("Click two points on the map to measure distance in metres")
        self._act_measure.triggered.connect(self._on_measure_toggled)
        self.addAction(self._act_measure)

        self._act_annotate = QAction("📝 Note", self)
        self._act_annotate.setCheckable(True)
        self._act_annotate.setStatusTip("Click to place a text annotation on the map")
        self._act_annotate.setToolTip("Click map to add a draggable text note; right-click to remove")
        self._act_annotate.triggered.connect(self._on_annotate_toggled)
        self.addAction(self._act_annotate)

        # Mutual exclusion for drawing modes
        self._draw_group = QActionGroup(self)
        self._draw_group.setExclusive(False)
        self._draw_group.addAction(self._act_boundary)
        self._draw_group.addAction(self._act_zone)
        self._draw_group.addAction(self._act_measure)
        self._draw_group.addAction(self._act_annotate)

        self.addSeparator()

        # Undo (Ctrl+Z) — reverses the last placement / drawing action.
        # Distinct from Cancel, which only aborts the *current* in-progress
        # drawing operation (e.g. mid-boundary).
        act_undo = QAction("⤺ Undo", self)
        act_undo.setShortcut("Ctrl+Z")
        act_undo.setStatusTip("Undo the last action (Ctrl+Z)")
        act_undo.setToolTip(
            "Undo the last placement or drawing action.\n"
            "Note: 'Cancel' only aborts the current drawing operation\n"
            "(mid-boundary etc.); use 'Undo' to revert a completed action."
        )
        act_undo.triggered.connect(self.undo_requested)
        self.addAction(act_undo)

        act_cancel = QAction("✕ Cancel", self)
        act_cancel.setStatusTip("Cancel the current in-progress drawing")
        act_cancel.setToolTip(
            "Abort the drawing operation in progress (e.g. discards an\n"
            "unfinished boundary, exits plant-placement mode).\n"
            "Does not affect already-placed items — use Undo for that."
        )
        act_cancel.triggered.connect(self._on_cancel)
        self.addAction(act_cancel)

    def _build_layers(self):
        bar = self.layers_bar
        bar.addWidget(QLabel("  Layers: "))

        self._act_satellite = QAction("🛰 Satellite", self)
        self._act_satellite.setCheckable(True)
        self._act_satellite.setStatusTip("Toggle satellite/OSM base map")
        self._act_satellite.toggled.connect(self.satellite_toggled)
        bar.addAction(self._act_satellite)

        self._act_boundary_layer = QAction("⬡ Boundary", self)
        self._act_boundary_layer.setCheckable(True)
        self._act_boundary_layer.setChecked(True)
        self._act_boundary_layer.setStatusTip("Toggle property boundary visibility")
        self._act_boundary_layer.toggled.connect(self.boundary_toggled)
        bar.addAction(self._act_boundary_layer)

        self._act_zones_layer = QAction("◎ Zones", self)
        self._act_zones_layer.setCheckable(True)
        self._act_zones_layer.setChecked(True)
        self._act_zones_layer.setStatusTip("Toggle permaculture zone circles visibility")
        self._act_zones_layer.toggled.connect(self.zones_toggled)
        bar.addAction(self._act_zones_layer)

        self._act_plants_layer = QAction("✿ Plants", self)
        self._act_plants_layer.setCheckable(True)
        self._act_plants_layer.setChecked(True)
        self._act_plants_layer.setStatusTip("Toggle plant markers visibility")
        self._act_plants_layer.toggled.connect(self.plants_toggled)
        bar.addAction(self._act_plants_layer)

        self._act_labels = QAction("Aa Labels", self)
        self._act_labels.setCheckable(True)
        self._act_labels.setStatusTip("Show/hide plant name labels on map")
        self._act_labels.setToolTip("Toggle permanent plant name labels on the map")
        self._act_labels.toggled.connect(self.labels_toggled)
        bar.addAction(self._act_labels)

        self._act_canopy = QAction("🌳 Canopy", self)
        self._act_canopy.setCheckable(True)
        self._act_canopy.setStatusTip("Show mature canopy spread preview")
        self._act_canopy.setToolTip("Toggle semi-transparent canopy circles showing mature plant spread")
        self._act_canopy.toggled.connect(self.canopy_toggled)
        bar.addAction(self._act_canopy)

        self._act_structures_layer = QAction("🏗 Structures", self)
        self._act_structures_layer.setCheckable(True)
        self._act_structures_layer.setChecked(True)
        self._act_structures_layer.setStatusTip("Toggle structures/hedgerows/shapes visibility")
        self._act_structures_layer.toggled.connect(self.structures_toggled)
        bar.addAction(self._act_structures_layer)

        self._act_snap = QAction("# Grid", self)
        self._act_snap.setCheckable(True)
        self._act_snap.setStatusTip("Snap plant placement to grid")
        self._act_snap.setToolTip("Enable 1m grid overlay; plant placement snaps to grid intersections")
        self._act_snap.toggled.connect(self.snap_toggled)
        bar.addAction(self._act_snap)

        act_clear_measure = QAction("✕ 📏", self)
        act_clear_measure.setStatusTip("Clear current measurement from map")
        act_clear_measure.setToolTip("Remove the measure line and distance label from the map")
        act_clear_measure.triggered.connect(self.measure_cleared)
        bar.addAction(act_clear_measure)

        bar.addSeparator()

        act_settings = QAction("⚙ Settings", self)
        act_settings.setStatusTip("Configure API keys and preferences")
        act_settings.triggered.connect(self.settings_requested)
        bar.addAction(act_settings)

        bar.addSeparator()

        # ── Zoom sensitivity ───────────────────────────────────────
        bar.addWidget(QLabel("  🔍 Zoom: "))
        self._zoom_combo = QComboBox()
        self._zoom_combo.addItems(["Fine (1.1×)", "Normal (1.26×)", "Fast (1.5×)", "Coarse (2×)"])
        self._zoom_combo.setCurrentIndex(0)
        self._zoom_combo.setToolTip(
            "Scroll-wheel zoom sensitivity per tick\n"
            "Fine ≈ 1.1× per scroll tick (smoothest)\n"
            "Coarse ≈ 2× per tick (original Leaflet default)"
        )
        self._zoom_combo.currentIndexChanged.connect(self._on_zoom_combo_changed)
        bar.addWidget(self._zoom_combo)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def attach_to(self, main_window):
        """Add Draw on the top row, Layers on a second row below it."""
        main_window.addToolBar(self)
        main_window.addToolBarBreak()
        main_window.addToolBar(self.layers_bar)

    # ── Internal handlers ─────────────────────────────────────────────────────

    def _on_boundary_toggled(self, checked: bool):
        if checked:
            self._uncheck_except(self._act_boundary)
            self.draw_boundary_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _on_zone_toggled(self, checked: bool):
        if checked:
            self._uncheck_except(self._act_zone)
            self.draw_zone_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _on_measure_toggled(self, checked: bool):
        if checked:
            self._uncheck_except(self._act_measure)
            self.measure_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _on_annotate_toggled(self, checked: bool):
        if checked:
            self._uncheck_except(self._act_annotate)
            self.annotate_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _uncheck_except(self, keep: QAction):
        for act in [self._act_boundary, self._act_zone,
                    self._act_measure, self._act_annotate]:
            if act is not keep:
                act.setChecked(False)

    def _on_cancel(self):
        self._act_boundary.setChecked(False)
        self._act_zone.setChecked(False)
        self._act_measure.setChecked(False)
        self._act_annotate.setChecked(False)
        self.cancel_draw_requested.emit()

    _ZOOM_LEVELS = ['fine', 'normal', 'fast', 'coarse']

    def _on_zoom_combo_changed(self, idx: int):
        level = self._ZOOM_LEVELS[idx] if 0 <= idx < len(self._ZOOM_LEVELS) else 'fine'
        self.zoom_step_changed.emit(level)

    # ── Public helpers ────────────────────────────────────────────────────────

    def reset_draw_buttons(self):
        """Uncheck all drawing buttons (called when a draw operation completes)."""
        self._act_boundary.setChecked(False)
        self._act_zone.setChecked(False)
        self._act_measure.setChecked(False)
        self._act_annotate.setChecked(False)

    def enter_plant_mode(self):
        """Called by plant panel 'Place on Map' — visually deactivate draw buttons."""
        self._act_boundary.setChecked(False)
        self._act_zone.setChecked(False)
        self._act_measure.setChecked(False)
        self._act_annotate.setChecked(False)
