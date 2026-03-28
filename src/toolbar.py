"""
toolbar.py — Top toolbar for drawing tools, layer toggles, and project actions.
"""

from PyQt6.QtWidgets import QToolBar, QLabel
from PyQt6.QtGui import QAction, QActionGroup, QIcon
from PyQt6.QtCore import pyqtSignal, Qt


class MainToolbar(QToolBar):
    """
    Signals emitted when user activates a tool or toggles a layer.
    The main window (app.py) connects these to the map widget.
    """

    # Drawing mode signals
    draw_boundary_requested   = pyqtSignal()
    draw_zone_requested       = pyqtSignal()
    measure_requested         = pyqtSignal()
    annotate_requested        = pyqtSignal()
    cancel_draw_requested     = pyqtSignal()

    # Layer visibility signals
    satellite_toggled  = pyqtSignal(bool)
    boundary_toggled   = pyqtSignal(bool)
    zones_toggled      = pyqtSignal(bool)
    plants_toggled     = pyqtSignal(bool)
    labels_toggled     = pyqtSignal(bool)
    canopy_toggled     = pyqtSignal(bool)
    snap_toggled       = pyqtSignal(bool)

    # Settings
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Tools", parent)
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._build()

    def _build(self):
        # ── Drawing group ──────────────────────────────────────────────────
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

        act_cancel = QAction("✕ Cancel", self)
        act_cancel.setStatusTip("Cancel current drawing operation")
        act_cancel.triggered.connect(self._on_cancel)
        self.addAction(act_cancel)

        self.addSeparator()

        # ── Layer toggles ──────────────────────────────────────────────────
        self.addWidget(QLabel("  Layers: "))

        self._act_satellite = QAction("🛰 Satellite", self)
        self._act_satellite.setCheckable(True)
        self._act_satellite.setStatusTip("Toggle satellite/OSM base map")
        self._act_satellite.toggled.connect(self.satellite_toggled)
        self.addAction(self._act_satellite)

        self._act_boundary_layer = QAction("⬡ Boundary", self)
        self._act_boundary_layer.setCheckable(True)
        self._act_boundary_layer.setChecked(True)
        self._act_boundary_layer.setStatusTip("Toggle property boundary visibility")
        self._act_boundary_layer.toggled.connect(self.boundary_toggled)
        self.addAction(self._act_boundary_layer)

        self._act_zones_layer = QAction("◎ Zones", self)
        self._act_zones_layer.setCheckable(True)
        self._act_zones_layer.setChecked(True)
        self._act_zones_layer.setStatusTip("Toggle permaculture zone circles visibility")
        self._act_zones_layer.toggled.connect(self.zones_toggled)
        self.addAction(self._act_zones_layer)

        self._act_plants_layer = QAction("✿ Plants", self)
        self._act_plants_layer.setCheckable(True)
        self._act_plants_layer.setChecked(True)
        self._act_plants_layer.setStatusTip("Toggle plant markers visibility")
        self._act_plants_layer.toggled.connect(self.plants_toggled)
        self.addAction(self._act_plants_layer)

        self._act_labels = QAction("Aa Labels", self)
        self._act_labels.setCheckable(True)
        self._act_labels.setStatusTip("Show/hide plant name labels on map")
        self._act_labels.setToolTip("Toggle permanent plant name labels on the map")
        self._act_labels.toggled.connect(self.labels_toggled)
        self.addAction(self._act_labels)

        self._act_canopy = QAction("🌳 Canopy", self)
        self._act_canopy.setCheckable(True)
        self._act_canopy.setStatusTip("Show mature canopy spread preview")
        self._act_canopy.setToolTip("Toggle semi-transparent canopy circles showing mature plant spread")
        self._act_canopy.toggled.connect(self.canopy_toggled)
        self.addAction(self._act_canopy)

        self._act_snap = QAction("# Grid", self)
        self._act_snap.setCheckable(True)
        self._act_snap.setStatusTip("Snap plant placement to grid")
        self._act_snap.setToolTip("Enable 1m grid overlay; plant placement snaps to grid intersections")
        self._act_snap.toggled.connect(self.snap_toggled)
        self.addAction(self._act_snap)

        self.addSeparator()

        act_settings = QAction("⚙ Settings", self)
        act_settings.setStatusTip("Configure API keys and preferences")
        act_settings.triggered.connect(self.settings_requested)
        self.addAction(act_settings)

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
