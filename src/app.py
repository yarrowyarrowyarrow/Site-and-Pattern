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
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QLabel, QMessageBox, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer

from src.map_widget  import MapWidget
from src.plant_panel import PlantPanel
from src.toolbar     import MainToolbar
from src.climate     import get_zone, zone_label
import src.project as project_io


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
        self.setWindowTitle("PermaDesign — Permaculture Landscape Designer")
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

        self._build_ui()
        self._connect_signals()
        self._start_autosave()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        self.toolbar = MainToolbar(self)
        self.addToolBar(self.toolbar)

        # Central area
        self.map_widget  = MapWidget(self)
        self.plant_panel = PlantPanel(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(self.plant_panel)

        # 70 / 30 split
        splitter.setSizes([700, 300])
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        self.plant_panel.setMinimumWidth(220)
        self.plant_panel.setMaximumWidth(480)

        # Apply dark sidebar style
        self.plant_panel.setStyleSheet(
            "QWidget { background-color: #1e2a1e; color: #c8e6c9; }"
        )

        self.setCentralWidget(splitter)

        # Status bar labels
        self._sb_coords  = QLabel("Lat: — , Lng: —")
        self._sb_zone    = QLabel("Zone: —")
        self._sb_mode    = QLabel("Mode: Ready")

        self._sb_coords.setMinimumWidth(220)
        self._sb_zone.setMinimumWidth(100)

        sb = QStatusBar(self)
        sb.addWidget(self._sb_coords)
        sb.addWidget(_vsep())
        sb.addWidget(self._sb_zone)
        sb.addWidget(_vsep())
        sb.addPermanentWidget(self._sb_mode)
        self.setStatusBar(sb)

        # Menu bar
        self._build_menu()

        # Window style
        self.setStyleSheet(_APP_STYLE)

    def _build_menu(self):
        mb = self.menuBar()

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

        act_exit = file_menu.addAction("E&xit")
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        b = self.map_widget.bridge

        # Map → status bar
        b.mouse_moved.connect(self._on_mouse_moved)

        # Map events → project state
        b.boundary_complete.connect(self._on_boundary_complete)
        b.plant_placed.connect(self._on_plant_placed)
        b.zone_center_placed.connect(self._on_zone_center_placed)
        b.map_ready.connect(self._on_map_ready)

        # Toolbar → map
        self.toolbar.draw_boundary_requested.connect(self._enter_boundary_mode)
        self.toolbar.draw_zone_requested.connect(self._enter_zone_mode)
        self.toolbar.cancel_draw_requested.connect(self._cancel_draw)

        self.toolbar.satellite_toggled.connect(self.map_widget.set_satellite_visible)
        self.toolbar.boundary_toggled.connect(self.map_widget.set_boundary_visible)
        self.toolbar.zones_toggled.connect(self.map_widget.set_zones_visible)
        self.toolbar.plants_toggled.connect(self.map_widget.set_plants_visible)

        # Plant panel → map (plant placement)
        self.plant_panel.place_plant_requested.connect(self._enter_plant_mode)

    # ── Map-ready ─────────────────────────────────────────────────────────────

    def _on_map_ready(self):
        self._set_mode_label("Ready")

    # ── Status bar updates ────────────────────────────────────────────────────

    def _on_mouse_moved(self, lat: float, lng: float):
        self._sb_coords.setText(f"Lat: {lat:.5f} , Lng: {lng:.5f}")

    def _set_zone_display(self, zone):
        self._current_zone = zone
        self._sb_zone.setText(zone_label(zone))
        self._project["properties"]["hardiness_zone"] = zone
        self.plant_panel.set_zone(zone)

    def _set_mode_label(self, text: str):
        self._sb_mode.setText(f"Mode: {text}")

    # ── Drawing modes ─────────────────────────────────────────────────────────

    def _enter_boundary_mode(self):
        self._current_mode = 'boundary'
        self.map_widget.set_mode('boundary')
        self._set_mode_label("Drawing boundary — click to add points, double-click or click first point to close")

    def _enter_zone_mode(self):
        self._current_mode = 'zone'
        self.map_widget.set_mode('zone')
        self._set_mode_label("Zone circles — click to place zone centre")

    def _enter_plant_mode(self, plant_id: int, common_name: str):
        self._current_mode = 'plant'
        self.map_widget.set_mode('plant', plant_id, common_name)
        self.toolbar.enter_plant_mode()
        self._set_mode_label(f"Placing: {common_name} — click map, press Esc to cancel")

    def _cancel_draw(self):
        self._current_mode = 'none'
        self.map_widget.cancel_draw()
        self._set_mode_label("Ready")
        self.toolbar.reset_draw_buttons()

    # ── Map event handlers ────────────────────────────────────────────────────

    def _on_boundary_complete(self, coords: list):
        """coords is a list of [lat, lng] pairs."""
        # Persist in project as GeoJSON Polygon (lng, lat order)
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") != "property_boundary"
        ]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "property_boundary"}
        })

        # Compute centroid for zone lookup
        lats = [pt[0] for pt in coords]
        lngs = [pt[1] for pt in coords]
        clat = sum(lats) / len(lats)
        clng = sum(lngs) / len(lngs)
        self._set_zone_display(get_zone(clat, clng))

        self._modified = True
        self.toolbar.reset_draw_buttons()
        self._set_mode_label("Boundary set — " + zone_label(self._current_zone))

    def _on_plant_placed(self, plant_id: int, common_name: str, lat: float, lng: float):
        self._placed_plants.append({
            "plant_id": plant_id, "common_name": common_name, "lat": lat, "lng": lng
        })
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "plant",
                "plant_id": plant_id,
                "common_name": common_name,
                "quantity": 1
            }
        })
        self.plant_panel.on_plant_placed(plant_id, common_name)
        self._modified = True

    def _on_zone_center_placed(self, lat: float, lng: float):
        # Remove previous zone centre from project
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") != "zone_center"
        ]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "zone_center",
                "zone_radii": [10, 30, 60, 120, 240]
            }
        })
        self._modified = True
        self.toolbar.reset_draw_buttons()
        self._set_mode_label("Zone circles placed")

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

        self._project      = project_io.new_project()
        self._project_path = None
        self._modified     = False
        self._placed_plants.clear()
        self._current_zone = None
        self._sb_zone.setText("Zone: —")
        self.map_widget.clear_all()
        self.plant_panel.clear_placed()
        self.plant_panel.set_zone(None)
        self.setWindowTitle("PermaDesign — New Design")
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

        self.map_widget.clear_all()
        data = project_io.project_to_map_data(proj)

        if data["boundary"]:
            self.map_widget.load_boundary(data["boundary"])
            lats = [p[0] for p in data["boundary"]]
            lngs = [p[1] for p in data["boundary"]]
            self._set_zone_display(
                get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs))
            )

        for p in data["plants"]:
            self.map_widget.load_plant_marker(
                p["plant_id"], p["common_name"], p["lat"], p["lng"]
            )
            self._placed_plants.append(p)

        self.plant_panel.load_placed(data["plants"])

        if data["zone_center"]:
            self.map_widget.load_zone_center(*data["zone_center"])

        name = proj.get("properties", {}).get("project_name", "Design")
        self.setWindowTitle(f"PermaDesign — {name}")

    def _on_save(self):
        if self._project_path:
            self._save_to_path(self._project_path)
        else:
            self._on_save_as()

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Design", "",
            "PermaDesign Files (*.perma.geojson);;GeoJSON (*.geojson)"
        )
        if not path:
            return
        if not path.endswith(".geojson"):
            path += ".perma.geojson"
        self._save_to_path(path)

    def _save_to_path(self, path: str):
        try:
            project_io.save_project(self._project, path)
            self._project_path = path
            self._modified     = False
            name = self._project["properties"].get("project_name", "Design")
            self.setWindowTitle(f"PermaDesign — {name}")
            self.statusBar().showMessage(f"Saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    # ── Autosave ──────────────────────────────────────────────────────────────

    def _start_autosave(self):
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(self.AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start()

    def _autosave(self):
        if not self._modified:
            return
        tmp = os.path.join(os.path.expanduser("~"), ".permadesign_autosave.perma.geojson")
        try:
            project_io.save_project(self._project, tmp)
        except Exception:
            pass

    # ── Window close ─────────────────────────────────────────────────────────

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
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_draw()
        else:
            super().keyPressEvent(event)


# ── Helper widgets ────────────────────────────────────────────────────────────

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
