"""
toolbar.py — Top toolbar for drawing tools, layer toggles, and project actions.
"""

from PyQt6.QtWidgets import QToolBar, QLabel, QSeparator
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
    cancel_draw_requested     = pyqtSignal()

    # Layer visibility signals
    satellite_toggled  = pyqtSignal(bool)
    boundary_toggled   = pyqtSignal(bool)
    zones_toggled      = pyqtSignal(bool)
    plants_toggled     = pyqtSignal(bool)

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

        # Mutual exclusion for drawing modes
        self._draw_group = QActionGroup(self)
        self._draw_group.setExclusive(False)
        self._draw_group.addAction(self._act_boundary)
        self._draw_group.addAction(self._act_zone)

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

    # ── Internal handlers ─────────────────────────────────────────────────────

    def _on_boundary_toggled(self, checked: bool):
        if checked:
            self._act_zone.setChecked(False)
            self.draw_boundary_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _on_zone_toggled(self, checked: bool):
        if checked:
            self._act_boundary.setChecked(False)
            self.draw_zone_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _on_cancel(self):
        self._act_boundary.setChecked(False)
        self._act_zone.setChecked(False)
        self.cancel_draw_requested.emit()

    # ── Public helpers ────────────────────────────────────────────────────────

    def reset_draw_buttons(self):
        """Uncheck all drawing buttons (called when a draw operation completes)."""
        self._act_boundary.setChecked(False)
        self._act_zone.setChecked(False)

    def enter_plant_mode(self):
        """Called by plant panel 'Place on Map' — visually deactivate draw buttons."""
        self._act_boundary.setChecked(False)
        self._act_zone.setChecked(False)
