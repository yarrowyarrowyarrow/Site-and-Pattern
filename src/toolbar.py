"""
toolbar.py — Top toolbars for drawing tools, view layout, and project actions.

Layout (two stacked rows):

  ┌────────────────────────────────────────────────────────────────┐
  │ Draw: ⬡ Boundary  📏 Measure  📝 Note  ⤺ Undo  ✕ Cancel        │
  ├────────────────────────────────────────────────────────────────┤
  │ View: 🛰 Satellite ⬡ Boundary 📏 Measurement # Grid▼            │
  │       ✿ Plants 🌳 Canopy 🏗 Structures … 🔍 Zoom: …             │
  └────────────────────────────────────────────────────────────────┘

The View row order is fixed: Satellite, Boundary, Measurement, Grid,
Plants, Canopy, Structures (per the UI spec). The Grid action exposes a
popup menu for base size (1×1 / 5×5 / 10×10 / 100×100 m), opacity, and
colour. The main click on Grid still toggles the snap on/off.
"""

from PyQt6.QtWidgets import (
    QToolBar, QLabel, QComboBox, QToolButton, QMenu, QWidget,
    QVBoxLayout, QHBoxLayout, QSlider, QPushButton, QColorDialog,
    QWidgetAction,
)
from PyQt6.QtGui import QAction, QActionGroup, QColor
from PyQt6.QtCore import pyqtSignal, Qt


class _GridSettingsMenu(QMenu):
    """Popup menu for Grid base size, opacity, and colour.

    Emits ``settings_changed`` with the full settings dict whenever the
    user changes anything. The toolbar then re-emits the values upward
    along with the current on/off state.
    """

    settings_changed = pyqtSignal(dict)

    SIZES_M = [1.0, 5.0, 10.0, 100.0]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._size_m  = 1.0
        self._opacity = 0.4
        self._color   = "#4a7a4a"
        self._build()

    def _build(self):
        # Size — radio actions for the four base sizes.
        size_label = QAction("Base size", self)
        size_label.setEnabled(False)
        self.addAction(size_label)

        self._size_group = QActionGroup(self)
        self._size_group.setExclusive(True)
        for s in self.SIZES_M:
            label = f"{int(s) if s.is_integer() else s} × {int(s) if s.is_integer() else s} m"
            act = QAction(label, self)
            act.setCheckable(True)
            if s == self._size_m:
                act.setChecked(True)
            act.setData(s)
            act.triggered.connect(self._on_size_chosen)
            self._size_group.addAction(act)
            self.addAction(act)

        self.addSeparator()

        # Opacity slider — embedded as a QWidgetAction so the menu can host it.
        op_widget = QWidget()
        op_layout = QVBoxLayout(op_widget)
        op_layout.setContentsMargins(8, 4, 8, 4)
        op_layout.setSpacing(2)
        op_layout.addWidget(QLabel("Opacity"))
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setMinimum(0)
        self._opacity_slider.setMaximum(100)
        self._opacity_slider.setValue(int(self._opacity * 100))
        self._opacity_slider.setMinimumWidth(180)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        op_layout.addWidget(self._opacity_slider)
        op_act = QWidgetAction(self)
        op_act.setDefaultWidget(op_widget)
        self.addAction(op_act)

        # Colour picker.
        col_widget = QWidget()
        col_layout = QHBoxLayout(col_widget)
        col_layout.setContentsMargins(8, 4, 8, 6)
        col_layout.addWidget(QLabel("Colour"))
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(24, 18)
        self._color_btn.setStyleSheet(self._color_btn_style())
        self._color_btn.clicked.connect(self._on_pick_color)
        col_layout.addWidget(self._color_btn)
        col_layout.addStretch(1)
        col_act = QWidgetAction(self)
        col_act.setDefaultWidget(col_widget)
        self.addAction(col_act)

    def _color_btn_style(self) -> str:
        return (
            f"background: {self._color}; border: 1px solid #6c6c6c; "
            f"border-radius: 3px;"
        )

    def _on_size_chosen(self):
        act = self.sender()
        if act is None:
            return
        try:
            self._size_m = float(act.data())
        except (TypeError, ValueError):
            return
        self._emit()

    def _on_opacity_changed(self, value: int):
        self._opacity = max(0.0, min(1.0, value / 100.0))
        self._emit()

    def _on_pick_color(self):
        color = QColorDialog.getColor(QColor(self._color), self, "Grid colour")
        if not color.isValid():
            return
        self._color = color.name()
        self._color_btn.setStyleSheet(self._color_btn_style())
        self._emit()

    def current_settings(self) -> dict:
        return {
            "size_m":  self._size_m,
            "opacity": self._opacity,
            "color":   self._color,
        }

    def _emit(self):
        self.settings_changed.emit(self.current_settings())


class MainToolbar(QToolBar):
    """The Draw toolbar (top row).

    Holds a sibling `layers_bar` QToolBar exposed for the main window to
    add on a second row. All signals — Draw, View, Zoom — live on this
    object so app.py wiring stays a single connection surface.
    """

    # Drawing mode signals
    draw_boundary_requested   = pyqtSignal()
    measure_requested         = pyqtSignal()
    annotate_requested        = pyqtSignal()
    select_requested          = pyqtSignal()
    cancel_draw_requested     = pyqtSignal()
    undo_requested            = pyqtSignal()
    redo_requested            = pyqtSignal()

    # View visibility signals
    satellite_toggled    = pyqtSignal(bool)
    boundary_toggled     = pyqtSignal(bool)
    measurements_toggled = pyqtSignal(bool)
    plants_toggled       = pyqtSignal(bool)
    canopy_toggled       = pyqtSignal(bool)
    structures_toggled   = pyqtSignal(bool)
    yard_photo_toggled   = pyqtSignal(bool)
    grid_settings_changed = pyqtSignal(dict)
    # ^ payload: {"enabled": bool, "size_m": float, "opacity": float, "color": str}

    # Zoom sensitivity changed ('fine'|'normal'|'fast'|'coarse')
    zoom_step_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Draw", parent)
        self.setMovable(False)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        # Sibling View bar — attached on a second row via attach_to().
        self.layers_bar = QToolBar("View", parent)
        self.layers_bar.setMovable(False)
        self.layers_bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        self._build_draw()
        self._build_view()

    # ── Construction ──────────────────────────────────────────────────────────

    def _build_draw(self):
        self.addWidget(QLabel("  Draw: "))

        self._act_boundary = QAction("⬡ Boundary", self)
        self._act_boundary.setCheckable(True)
        self._act_boundary.setStatusTip("Draw property boundary polygon")
        self._act_boundary.setToolTip("Click to add points; click first point (or double-click) to close")
        self._act_boundary.triggered.connect(self._on_boundary_toggled)
        self.addAction(self._act_boundary)

        self._act_measure = QAction("📏 Measure", self)
        self._act_measure.setCheckable(True)
        self._act_measure.setStatusTip("Click two points to measure distance")
        self._act_measure.setToolTip(
            "Click two points to add a measurement.\n"
            "Right-click an existing measurement to delete it.\n"
            "Use the View bar 'Measurement' toggle to hide/show all of them."
        )
        self._act_measure.triggered.connect(self._on_measure_toggled)
        self.addAction(self._act_measure)

        self._act_annotate = QAction("📝 Note", self)
        self._act_annotate.setCheckable(True)
        self._act_annotate.setStatusTip("Click to place a text annotation on the map")
        self._act_annotate.setToolTip("Click map to add a draggable text note; right-click to remove")
        self._act_annotate.triggered.connect(self._on_annotate_toggled)
        self.addAction(self._act_annotate)

        self._act_select = QAction("⬚ Select", self)
        self._act_select.setCheckable(True)
        self._act_select.setStatusTip("Drag a box to select plants, structures, boundaries…")
        self._act_select.setToolTip(
            "Box-select: drag a rectangle on the map to select everything inside\n"
            "(plants, structures, boundaries, sun sectors). Then drag the\n"
            "selection to move it, or press Delete. (Shift+drag works any time too.)"
        )
        self._act_select.triggered.connect(self._on_select_toggled)
        self.addAction(self._act_select)

        # Mutual exclusion for drawing modes
        self._draw_group = QActionGroup(self)
        self._draw_group.setExclusive(False)
        self._draw_group.addAction(self._act_boundary)
        self._draw_group.addAction(self._act_measure)
        self._draw_group.addAction(self._act_annotate)
        self._draw_group.addAction(self._act_select)

        self.addSeparator()

        # Undo (Ctrl+Z) / Redo (Ctrl+Shift+Z) — reverse / re-apply the last
        # action. Distinct from Cancel, which only aborts the *current*
        # in-progress drawing operation (e.g. mid-boundary). Held as
        # attributes + disabled initially so set_undo_redo_enabled() can grey
        # them out when the matching stack is empty.
        # Shortcuts live on the Edit-menu actions (Ctrl+Z / Ctrl+Shift+Z) to
        # avoid an ambiguous-shortcut clash; these toolbar buttons are
        # click-only, with the key shown in the status tip.
        self._act_undo = QAction("⤺ Undo", self)
        self._act_undo.setStatusTip("Undo the last action (Ctrl+Z)")
        self._act_undo.setToolTip(
            "Undo the last action — placements, removals, edits, imports and\n"
            "overlay toggles (Ctrl+Z)."
        )
        self._act_undo.setEnabled(False)
        self._act_undo.triggered.connect(self.undo_requested)
        self.addAction(self._act_undo)

        self._act_redo = QAction("⤻ Redo", self)
        self._act_redo.setStatusTip("Redo the last undone action (Ctrl+Shift+Z)")
        self._act_redo.setToolTip("Re-apply the action you just undid (Ctrl+Shift+Z).")
        self._act_redo.setEnabled(False)
        self._act_redo.triggered.connect(self.redo_requested)
        self.addAction(self._act_redo)

        act_cancel = QAction("✕ Cancel", self)
        act_cancel.setStatusTip("Cancel the current in-progress drawing")
        act_cancel.setToolTip(
            "Abort the drawing operation in progress (e.g. discards an\n"
            "unfinished boundary, exits plant-placement mode).\n"
            "Does not affect already-placed items — use Undo for that."
        )
        act_cancel.triggered.connect(self._on_cancel)
        self.addAction(act_cancel)

    def set_undo_redo_enabled(self, undo: bool, redo: bool):
        """Grey out the toolbar Undo / Redo buttons when their stack is empty.
        Driven by PersistenceController._refresh_actions alongside the Edit-menu
        actions."""
        self._act_undo.setEnabled(bool(undo))
        self._act_redo.setEnabled(bool(redo))

    def _build_view(self):
        # NOTE: ordering is fixed by spec — Satellite, Boundary,
        # Measurement, Grid, Plants, Canopy, Structures.
        bar = self.layers_bar
        bar.addWidget(QLabel("  View: "))

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

        # Measurement visibility — toggles whether existing measurements
        # are shown. Does NOT delete them; right-click an individual line
        # to remove just it.
        self._act_measurements_layer = QAction("📏 Measurement", self)
        self._act_measurements_layer.setCheckable(True)
        self._act_measurements_layer.setChecked(True)
        self._act_measurements_layer.setStatusTip(
            "Show/hide existing measurements (does not delete them)"
        )
        self._act_measurements_layer.setToolTip(
            "Hide every placed measurement without deleting it.\n"
            "Right-click any individual measurement to delete just that one."
        )
        self._act_measurements_layer.toggled.connect(self.measurements_toggled)
        bar.addAction(self._act_measurements_layer)

        # Grid — checkable QToolButton with a popup menu for size /
        # opacity / colour. Click toggles enabled; the menu chevron
        # opens the settings.
        self._grid_menu = _GridSettingsMenu(self)
        self._grid_menu.settings_changed.connect(self._emit_grid_settings)

        self._grid_btn = QToolButton(bar)
        self._grid_btn.setText("# Grid")
        self._grid_btn.setCheckable(True)
        self._grid_btn.setChecked(False)
        self._grid_btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self._grid_btn.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self._grid_btn.setMenu(self._grid_menu)
        self._grid_btn.setStatusTip(
            "Toggle grid overlay; click ▾ for size / opacity / colour"
        )
        self._grid_btn.setToolTip(
            "Snap-to-grid overlay.\n"
            "Click to toggle on/off; the ▾ chevron opens base size,\n"
            "opacity and colour controls."
        )
        self._grid_btn.toggled.connect(self._emit_grid_settings)
        bar.addWidget(self._grid_btn)

        self._act_plants_layer = QAction("✿ Plants", self)
        self._act_plants_layer.setCheckable(True)
        self._act_plants_layer.setChecked(True)
        self._act_plants_layer.setStatusTip("Toggle plant markers visibility")
        self._act_plants_layer.toggled.connect(self.plants_toggled)
        bar.addAction(self._act_plants_layer)

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

        # Yard photo — the baked top-down render of an imported Gaussian-splat
        # scan (V1.65). Disabled until a project actually has one; enabled via
        # set_yard_photo_available().
        self._act_yard_photo = QAction("📷 Yard photo", self)
        self._act_yard_photo.setCheckable(True)
        self._act_yard_photo.setEnabled(False)
        self._act_yard_photo.setStatusTip(
            "Show the photoreal top-down scan of your yard (from Import Yard Scan)")
        self._act_yard_photo.toggled.connect(self.yard_photo_toggled)
        bar.addAction(self._act_yard_photo)

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

    def set_yard_photo_available(self, available: bool, *, checked=None):
        """Enable/disable the "Yard photo" View toggle (a project has a baked
        Gaussian-splat overlay or not). Optionally set its checked state
        without re-emitting ``yard_photo_toggled``."""
        self._act_yard_photo.setEnabled(bool(available))
        if not available:
            checked = False
        if checked is not None:
            blocked = self._act_yard_photo.blockSignals(True)
            self._act_yard_photo.setChecked(bool(checked))
            self._act_yard_photo.blockSignals(blocked)

    def attach_to(self, main_window):
        """Add Draw on the top row, View on a second row below it."""
        main_window.addToolBar(self)
        main_window.addToolBarBreak()
        main_window.addToolBar(self.layers_bar)

    def attach_to_layout(self, layout):
        """Add Draw + View as stacked widgets inside a vertical layout.

        Lets the side panel float free of the QMainWindow toolbar area so
        it can extend from just below the menu bar to the status bar,
        while the toolbars only span the map column on the left.
        """
        # The QToolBar is reparented when added to a layout; clear the
        # QMainWindow-side state in case attach_to() was called earlier.
        self.setParent(None)
        self.layers_bar.setParent(None)
        layout.addWidget(self)
        layout.addWidget(self.layers_bar)

    # ── Internal handlers ─────────────────────────────────────────────────────

    def _on_boundary_toggled(self, checked: bool):
        if checked:
            self._uncheck_except(self._act_boundary)
            self.draw_boundary_requested.emit()
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

    def _on_select_toggled(self, checked: bool):
        if checked:
            self._uncheck_except(self._act_select)
            self.select_requested.emit()
        else:
            self.cancel_draw_requested.emit()

    def _uncheck_except(self, keep: QAction):
        for act in [self._act_boundary, self._act_measure, self._act_annotate,
                    self._act_select]:
            if act is not keep:
                act.setChecked(False)

    def _on_cancel(self):
        self._act_boundary.setChecked(False)
        self._act_measure.setChecked(False)
        self._act_annotate.setChecked(False)
        self._act_select.setChecked(False)
        self.cancel_draw_requested.emit()

    def _emit_grid_settings(self, *_):
        """Re-emit the combined grid state whenever enabled/menu changes."""
        payload = dict(self._grid_menu.current_settings())
        payload["enabled"] = bool(self._grid_btn.isChecked())
        self.grid_settings_changed.emit(payload)

    _ZOOM_LEVELS = ['fine', 'normal', 'fast', 'coarse']

    def _on_zoom_combo_changed(self, idx: int):
        level = self._ZOOM_LEVELS[idx] if 0 <= idx < len(self._ZOOM_LEVELS) else 'fine'
        self.zoom_step_changed.emit(level)

    # ── Public helpers ────────────────────────────────────────────────────────

    def reset_draw_buttons(self):
        """Uncheck all drawing buttons (called when a draw operation completes)."""
        self._act_boundary.setChecked(False)
        self._act_measure.setChecked(False)
        self._act_annotate.setChecked(False)

    def enter_plant_mode(self):
        """Called by plant panel 'Place on Map' — visually deactivate draw buttons."""
        self._act_boundary.setChecked(False)
        self._act_measure.setChecked(False)
        self._act_annotate.setChecked(False)
