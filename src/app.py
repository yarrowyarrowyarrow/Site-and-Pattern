import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .climate import centroid, get_hardiness_zone
from .db.plants import init_db
from .db.seed_data import main as seed_db
from .guild_panel import GuildPanel
from .map_widget import MapWidget
from .plant_panel import PlantPanel
from .project import ProjectManager
from .toolbar import MainToolBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PermaDesign — Permaculture Landscape Designer")
        self.resize(1400, 900)

        # Initialize database
        seed_db()

        # Project manager
        self.project = ProjectManager()

        # Style
        self.setStyleSheet("""
            QMainWindow { background: #2b2b2b; }
            QTabWidget::pane { border: 1px solid #555; }
            QTabBar::tab { background: #3c3c3c; color: #ddd; padding: 8px 16px; }
            QTabBar::tab:selected { background: #4a4a4a; color: #fff; }
            QListWidget { background: #3c3c3c; color: #ddd; border: 1px solid #555; }
            QListWidget::item:selected { background: #5a7a5a; }
            QTextEdit { background: #3c3c3c; color: #ddd; border: 1px solid #555; }
            QLineEdit { background: #3c3c3c; color: #ddd; border: 1px solid #555; padding: 4px; }
            QComboBox { background: #3c3c3c; color: #ddd; border: 1px solid #555; padding: 4px; }
            QPushButton { background: #4a6a4a; color: #fff; border: none; padding: 6px 12px; border-radius: 3px; }
            QPushButton:hover { background: #5a7a5a; }
            QPushButton:disabled { background: #555; color: #888; }
            QGroupBox { color: #ddd; border: 1px solid #555; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { subcontrol-origin: margin; padding: 0 4px; }
            QLabel { color: #ddd; }
            QStatusBar { background: #2b2b2b; color: #aaa; }
            QToolBar { background: #333; border-bottom: 1px solid #555; spacing: 4px; }
            QToolBar QToolButton { color: #ddd; padding: 4px 8px; }
            QMenuBar { background: #333; color: #ddd; }
            QMenuBar::item:selected { background: #555; }
            QMenu { background: #3c3c3c; color: #ddd; }
            QMenu::item:selected { background: #5a7a5a; }
        """)

        self._build_ui()
        self._connect_signals()
        self._build_menu()

    def _build_ui(self):
        # Central splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Map (left, 70%)
        self.map_widget = MapWidget()
        splitter.addWidget(self.map_widget)

        # Side panel (right, 30%)
        side_panel = QTabWidget()

        self.plant_panel = PlantPanel()
        side_panel.addTab(self.plant_panel, "Plants")

        self.guild_panel = GuildPanel()
        side_panel.addTab(self.guild_panel, "Guilds")

        splitter.addWidget(side_panel)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        self.setCentralWidget(splitter)

        # Toolbar
        self.toolbar = MainToolBar()
        self.addToolBar(self.toolbar)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.coord_label = QWidget()
        self.status_bar.showMessage("Ready — Center: Edmonton, AB")

    def _build_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        file_menu.addAction("New", self._on_new)
        file_menu.addAction("Open...", self._on_open)
        file_menu.addSeparator()
        file_menu.addAction("Save", self._on_save)
        file_menu.addAction("Save As...", self._on_save_as)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

    def _connect_signals(self):
        bridge = self.map_widget.bridge

        # Mouse move → status bar coordinates
        bridge.mouseMoved.connect(self._on_mouse_move)

        # Boundary complete → zone lookup
        bridge.boundaryCompleted.connect(self._on_boundary_complete)

        # Plant placement
        self.plant_panel.placeRequested.connect(self._on_place_plant_requested)
        bridge.plantPlaced.connect(self._on_plant_placed)

        # Guild placement
        self.guild_panel.placeGuildRequested.connect(self._on_place_guild_requested)
        bridge.guildPlaced.connect(self._on_guild_placed)

        # Zone circles
        bridge.zonesDrawn.connect(self._on_zones_drawn)

        # Toolbar
        self.toolbar.drawBoundary.connect(self._on_draw_boundary)
        self.toolbar.drawZones.connect(self._on_draw_zones)
        self.toolbar.toggleSatellite.connect(self.map_widget.toggle_satellite)
        self.toolbar.cancelDrawing.connect(self.map_widget.clear_pending)

    def _on_mouse_move(self, lat, lng):
        zone = get_hardiness_zone(lat, lng)
        zone_text = f"Zone {zone}" if zone is not None else "Zone ?"
        self.status_bar.showMessage(
            f"Lat: {lat:.5f}  Lng: {lng:.5f}  |  {zone_text}"
            + (f"  |  Project Zone: {self.project.hardiness_zone}" if self.project.hardiness_zone else "")
        )

    def _on_boundary_complete(self, coords_json):
        coords = json.loads(coords_json)  # [[lng, lat], ...]
        self.project.boundary_coords = coords
        self.project.modified = True

        lat, lng = centroid(coords)
        if lat and lng:
            zone = get_hardiness_zone(lat, lng)
            self.project.hardiness_zone = zone
            self.status_bar.showMessage(
                f"Boundary set — Hardiness Zone: {zone}"
            )

    def _on_draw_boundary(self):
        self.map_widget.set_drawing_mode("boundary")
        self.status_bar.showMessage("Click to draw boundary. Double-click or click first point to close.")

    def _on_draw_zones(self):
        lat, ok1 = QInputDialog.getDouble(
            self, "Zone Center", "Center latitude:", 53.5461, -90, 90, 5
        )
        if not ok1:
            return
        lng, ok2 = QInputDialog.getDouble(
            self, "Zone Center", "Center longitude:", -113.4938, -180, 180, 5
        )
        if not ok2:
            return

        radii = [5, 15, 30, 60, 120]
        self.map_widget.draw_zone_circles(lat, lng, radii)

    def _on_zones_drawn(self, lat, lng, radii_json):
        radii = json.loads(radii_json)
        self.project.zone_center = {"lat": lat, "lng": lng, "radii": radii}
        self.project.modified = True

    def _on_place_plant_requested(self, plant_id, name, plant_type):
        self.map_widget.set_pending_plant(plant_id, name, plant_type)
        self.status_bar.showMessage(f"Click map to place: {name}")

    def _on_plant_placed(self, plant_id, name, lat, lng):
        self.project.placed_plants.append({
            "plant_id": plant_id,
            "common_name": name,
            "plant_type": "",
            "lat": lat,
            "lng": lng
        })
        self.plant_panel.add_placed_plant(plant_id, name)
        self.project.modified = True
        self.status_bar.showMessage(f"Placed: {name}")

    def _on_place_guild_requested(self, guild_data):
        self.map_widget.set_pending_guild(guild_data)
        self.status_bar.showMessage(f"Click map to place guild: {guild_data.get('name', '')}")

    def _on_guild_placed(self, guild_json, lat, lng):
        guild_data = json.loads(guild_json)
        self.project.placed_guilds.append({
            "guild_data": guild_data,
            "lat": lat,
            "lng": lng
        })
        self.project.modified = True
        self.status_bar.showMessage(f"Placed guild: {guild_data.get('name', '')}")

    def _on_new(self):
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save current project before creating a new one?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
            elif reply == QMessageBox.StandardButton.Cancel:
                return

        self.project.new_project()
        self.map_widget.clear_all()
        self.plant_panel.clear_placed()
        self.status_bar.showMessage("New project created")

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "",
            "PermaDesign Files (*.perma.geojson);;GeoJSON Files (*.geojson *.json)"
        )
        if not path:
            return

        try:
            self.project.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))
            return

        # Reload map elements
        self.map_widget.clear_all()
        self.plant_panel.clear_placed()

        if self.project.boundary_coords:
            self.map_widget.load_boundary(self.project.boundary_coords)

        for p in self.project.placed_plants:
            self.map_widget.load_plant(
                p["plant_id"], p["common_name"], p.get("plant_type", ""), p["lat"], p["lng"]
            )
            self.plant_panel.add_placed_plant(p["plant_id"], p["common_name"])

        if self.project.zone_center:
            zc = self.project.zone_center
            self.map_widget.load_zones(zc["lat"], zc["lng"], zc["radii"])

        for g in self.project.placed_guilds:
            self.map_widget.load_guild(g["guild_data"], g["lat"], g["lng"])

        if self.project.boundary_coords:
            self.map_widget.fit_to_boundary()

        zone_text = f" — Zone {self.project.hardiness_zone}" if self.project.hardiness_zone else ""
        self.status_bar.showMessage(f"Loaded: {self.project.project_name}{zone_text}")
        self.setWindowTitle(f"PermaDesign — {self.project.project_name}")

    def _on_save(self):
        if not self.project.file_path:
            self._on_save_as()
            return
        try:
            self.project.save()
            self.status_bar.showMessage(f"Saved: {self.project.file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", f"{self.project.project_name}.perma.geojson",
            "PermaDesign Files (*.perma.geojson)"
        )
        if not path:
            return

        name, ok = QInputDialog.getText(
            self, "Project Name", "Name:", text=self.project.project_name
        )
        if ok and name.strip():
            self.project.project_name = name.strip()

        try:
            self.project.save(path)
            self.setWindowTitle(f"PermaDesign — {self.project.project_name}")
            self.status_bar.showMessage(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def closeEvent(self, event):
        if self.project.modified:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "Save before exiting?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
