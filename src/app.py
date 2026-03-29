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
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QLabel, QMessageBox, QFileDialog, QSizePolicy,
    QInputDialog, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut

from src.map_widget       import MapWidget
from src.plant_panel      import PlantPanel
from src.guild_panel      import GuildPanel
from src.structure_panel  import StructurePanel
from src.analysis_panel   import AnalysisPanel
from src.toolbar          import MainToolbar
from src.climate          import get_zone, zone_label
from src.settings         import SettingsDialog, get_api_keys
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

        # Undo/redo stacks
        self._undo_stack: list[dict] = []   # each entry: {action, data}
        self._redo_stack: list[dict] = []
        self._max_undo = 50

        self._build_ui()
        self._connect_signals()
        self._start_autosave()
        self._load_api_keys()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # Toolbar
        self.toolbar = MainToolbar(self)
        self.addToolBar(self.toolbar)

        # Central area
        self.map_widget      = MapWidget(self)
        self.plant_panel     = PlantPanel(self)
        self.guild_panel     = GuildPanel(self)
        self.structure_panel = StructurePanel(self)
        self.analysis_panel  = AnalysisPanel(self)

        # Tabbed side panel: Plants + Guilds + Structures + Analysis
        self._side_tabs = QTabWidget()
        self._side_tabs.addTab(self.plant_panel, "Plants")
        self._side_tabs.addTab(self.guild_panel, "Guilds")
        self._side_tabs.addTab(self.structure_panel, "Structures")
        self._side_tabs.addTab(self.analysis_panel, "Analysis")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(self._side_tabs)

        # 70 / 30 split
        splitter.setSizes([700, 300])
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        self._side_tabs.setMinimumWidth(220)
        self._side_tabs.setMaximumWidth(480)

        # Apply dark sidebar style
        self._side_tabs.setStyleSheet(
            "QWidget { background-color: #1e2a1e; color: #c8e6c9; }"
        )

        self.setCentralWidget(splitter)

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

        # Window style
        self.setStyleSheet(_APP_STYLE)

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

        act_shopping = file_menu.addAction("Export &Shopping List…")
        act_shopping.setStatusTip("Export a list of all placed plants with quantities")
        act_shopping.triggered.connect(self._on_export_shopping_list)

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
        self.toolbar.measure_requested.connect(self._enter_measure_mode)
        self.toolbar.annotate_requested.connect(self._enter_annotate_mode)
        self.toolbar.cancel_draw_requested.connect(self._cancel_draw)

        self.toolbar.satellite_toggled.connect(self.map_widget.set_satellite_visible)
        self.toolbar.boundary_toggled.connect(self.map_widget.set_boundary_visible)
        self.toolbar.zones_toggled.connect(self.map_widget.set_zones_visible)
        self.toolbar.plants_toggled.connect(self.map_widget.set_plants_visible)
        self.toolbar.labels_toggled.connect(self.map_widget.set_labels_visible)
        self.toolbar.canopy_toggled.connect(self.map_widget.set_canopy_visible)
        self.toolbar.snap_toggled.connect(
            lambda on: self.map_widget.set_snap_enabled(on)
        )

        # Plant panel → map (plant placement + colour)
        self.plant_panel.place_plant_requested.connect(self._enter_plant_mode)
        self.plant_panel.color_changed.connect(self._on_plant_color_changed)

        # Map → remove plant marker
        b.plant_removed.connect(self._on_plant_removed)

        # Map → annotations
        b.annotate_requested.connect(self._on_annotate_requested)
        b.annotation_removed.connect(self._on_annotation_removed)

        # Toolbar → settings
        self.toolbar.settings_requested.connect(self._on_settings)

        # Guild panel → map (guild placement)
        self.guild_panel.placeGuildRequested.connect(self._enter_guild_mode)

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

        # Toolbar → structures layer toggle
        self.toolbar.structures_toggled.connect(self.map_widget.set_structures_visible)

        # Analysis panel → map (A1-A4)
        self.analysis_panel.sun_path_requested.connect(self._on_sun_path_requested)
        self.analysis_panel.sun_path_cleared.connect(self.map_widget.clear_sun_path)
        self.analysis_panel.sector_requested.connect(self._on_sector_requested)
        self.analysis_panel.sector_cleared.connect(self.map_widget.clear_sectors)
        self.analysis_panel.contour_requested.connect(self._on_contour_requested)
        self.analysis_panel.contour_cleared.connect(self._on_contour_cleared)
        self.analysis_panel.wind_requested.connect(self._on_wind_requested)
        self.analysis_panel.wind_cleared.connect(self.map_widget.clear_wind_overlay)

        # Map → contour complete
        b.contour_complete.connect(self._on_contour_complete)

    # ── Map-ready ─────────────────────────────────────────────────────────────

    def _on_map_ready(self):
        self._set_mode_label("Ready")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _load_api_keys(self):
        """Push stored API keys into the plant panel on startup."""
        kid, ksec = get_api_keys()
        self.plant_panel.set_api_keys(kid, ksec)

    def _on_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._load_api_keys()

    def _on_plant_color_changed(self, plant_id: int, hex_color: str):
        """Update all existing markers for this plant on the map."""
        self.map_widget.update_marker_color(plant_id, hex_color)

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

    def _mark_modified(self):
        self._modified = True
        if not self.windowTitle().endswith(' *'):
            self.setWindowTitle(self.windowTitle() + ' *')

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
        self._current_mode = 'boundary'
        self.map_widget.set_mode('boundary')
        self._set_mode_label("Drawing boundary — click to add points, double-click or click first point to close")

    def _enter_zone_mode(self):
        self._current_mode = 'zone'
        self.map_widget.set_mode('zone')
        self._set_mode_label("Zone circles — click to place zone centre")

    def _enter_plant_mode(self, plant_id: int, common_name: str,
                          quantity: int = 1):
        self._current_mode = 'plant'
        spacing_m, plant_type, custom_color = self._plant_info(plant_id)
        self.map_widget.set_mode('plant', plant_id, common_name, spacing_m,
                                 plant_type, quantity, custom_color)
        self.toolbar.enter_plant_mode()
        qty_str = f" ×{quantity}" if quantity > 1 else ""
        self._set_mode_label(
            f"Placing: {common_name}{qty_str} — click map, press Esc to cancel"
        )

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
        self._current_mode = 'measure'
        self.map_widget.set_mode('measure')
        self._set_mode_label("Measure — click two points to see distance")

    def _enter_annotate_mode(self):
        self._current_mode = 'annotate'
        self.map_widget.set_mode('annotate')
        self._set_mode_label("Annotate — click map to place a note")

    def _on_annotate_requested(self, lat: float, lng: float):
        text, ok = QInputDialog.getText(
            self, "Add Note", "Note text:", text=""
        )
        if not ok or not text.strip():
            return
        ann_id = f"ann_{int(lat*1e6)}_{int(lng*1e6)}_{id(self)}"
        self.map_widget.place_annotation(ann_id, lat, lng, text.strip())
        # Save to project
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "annotation",
                "annotation_id": ann_id,
                "text": text.strip(),
            }
        })
        self._mark_modified()

    def _on_annotation_removed(self, ann_id: str):
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("annotation_id") != ann_id
        ]
        self._mark_modified()

    # ── Structure / Hedgerow / Shape modes ──────────────────────────────────

    def _enter_structure_mode(self, struct_def: dict):
        self._current_mode = 'structure'
        self.map_widget.set_structure_mode(struct_def)
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            f"Placing: {struct_def.get('icon', '')} {struct_def.get('name', 'Structure')} — click map, Esc to cancel"
        )

    def _on_structure_placed(self, struct_id: str, name: str, lat: float, lng: float, size_m: float):
        from src.db.structures import get_structure
        struct_def = get_structure(struct_id)
        if struct_def:
            struct_def = dict(struct_def)
            struct_def["size_m"] = size_m
        else:
            struct_def = {"id": struct_id, "name": name, "size_m": size_m}

        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "structure",
                "struct_id": struct_id,
                "name": name,
                "size_m": size_m,
                "struct_def": struct_def,
            }
        })
        self._mark_modified()
        self.statusBar().showMessage(f"Placed {name}", 2000)

    def _on_structure_removed(self, marker_id: str, struct_id: str, lat: float, lng: float):
        kept = []
        removed = False
        for f in self._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (not removed
                    and props.get("element_type") == "structure"
                    and props.get("struct_id") == struct_id
                    and coords
                    and abs(coords[1] - lat) < 1e-7
                    and abs(coords[0] - lng) < 1e-7):
                removed = True
            else:
                kept.append(f)
        self._project["features"] = kept
        self._mark_modified()

    def _enter_hedgerow_mode(self, hedge_config: dict):
        self._current_mode = 'hedgerow'
        self.map_widget.set_hedgerow_mode(hedge_config)
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Drawing hedgerow — click to add points, double-click to finish"
        )

    def _on_hedgerow_complete(self, hedge_id: str, points_json: str, species: str,
                               style: str, length_m: float, num_plants: int):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON LineString (lng, lat order)
        coords = [[pt[1], pt[0]] for pt in points]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "element_type": "hedgerow",
                "hedge_id": hedge_id,
                "species": species,
                "style": style,
                "length_m": length_m,
                "num_plants": num_plants,
                "color": "#4caf50",
                "width_m": 1.5,
                "spacing_m": 1.0,
            }
        })
        self._mark_modified()
        self._set_mode_label("Ready")
        self.statusBar().showMessage(
            f"Hedgerow placed: {length_m:.1f}m, ~{num_plants} plants", 3000
        )

    def _on_hedgerow_removed(self, hedge_id: str, points_json: str):
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("hedge_id") != hedge_id
        ]
        self._mark_modified()

    def _enter_shape_mode(self, shape_config: dict):
        self._current_mode = 'shape'
        self.map_widget.set_shape_mode(shape_config)
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            "Drawing shape — click points, double-click or click first point to close"
        )

    def _on_shape_complete(self, shape_id: str, points_json: str, label: str,
                            shape_type: str, fill_color: str, stroke_color: str,
                            fill_opacity: float, dash_array: str, area_m2: float):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON Polygon (lng, lat; closed ring)
        ring = [[pt[1], pt[0]] for pt in points]
        ring.append(ring[0])  # close the ring
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "custom_shape",
                "shape_id": shape_id,
                "label": label,
                "shape_type": shape_type,
                "fill_color": fill_color,
                "stroke_color": stroke_color,
                "fill_opacity": fill_opacity,
                "dash_array": dash_array,
                "area_m2": area_m2,
            }
        })
        self._mark_modified()
        self._set_mode_label("Ready")
        area_str = f"{area_m2:.1f} m²" if area_m2 < 10000 else f"{area_m2/10000:.2f} ha"
        self.statusBar().showMessage(
            f"Shape placed: {label or shape_type} ({area_str})", 3000
        )

    def _on_shape_removed(self, shape_id: str):
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("shape_id") != shape_id
        ]
        self._mark_modified()

    # ── Analysis overlays (A1-A4) ──────────────────────────────────────────

    def _on_sun_path_requested(self, config: dict):
        """A1: Compute sun positions and send to map for rendering."""
        from datetime import date as _date
        from src.solar import sun_path_for_date, sunrise_sunset, EDMONTON_LAT, EDMONTON_LNG

        d = _date.fromisoformat(config["date"])
        # Use boundary centroid if available, else Edmonton default
        lat, lng = EDMONTON_LAT, EDMONTON_LNG
        for f in self._project.get("features", []):
            if f.get("properties", {}).get("element_type") == "property_boundary":
                ring = f["geometry"]["coordinates"][0]
                lat = sum(pt[1] for pt in ring) / len(ring)
                lng = sum(pt[0] for pt in ring) / len(ring)
                break

        positions = sun_path_for_date(lat, lng, d, steps=72)
        sr, ss = sunrise_sunset(lat, lng, d)

        pos_data = [
            {"altitude": p.altitude, "azimuth": p.azimuth, "hour": p.hour}
            for p in positions
        ]

        self.map_widget.draw_sun_path({
            "positions": pos_data,
            "date_label": config.get("date_label", d.isoformat()),
            "show_shadows": config.get("show_shadows", True),
            "show_shadow_length": config.get("show_shadow_length", False),
            "sunrise_hour": sr,
            "sunset_hour": ss,
        })

        # Update info label
        noon_alt = max((p.altitude for p in positions), default=0)
        daylight = ss - sr
        self.analysis_panel.set_sun_info(
            f"Sunrise: {_fmt_time(sr)} | Sunset: {_fmt_time(ss)}\n"
            f"Daylight: {daylight:.1f} hrs | Max altitude: {noon_alt:.1f}°"
        )
        self._set_mode_label(f"Sun path: {config.get('date_label', d.isoformat())}")

    def _on_sector_requested(self, config: dict):
        """A2: Draw sector analysis wedges."""
        self.map_widget.draw_sectors(config)
        names = [s["name"] for s in config.get("sectors", [])]
        self._set_mode_label(f"Sectors: {', '.join(names)}")

    def _on_contour_requested(self, config: dict):
        """A3: Enter contour drawing mode."""
        self._current_mode = 'contour'
        self.map_widget.set_contour_mode(config)
        self.toolbar.reset_draw_buttons()
        elev = config.get("elevation_m", 0)
        self._set_mode_label(
            f"Drawing contour at {elev:.1f}m — click points, double-click to finish"
        )

    def _on_contour_complete(self, points_json: str, elevation: float, color: str):
        """Save contour line to project."""
        import json as _json
        points = _json.loads(points_json)
        coords = [[pt[1], pt[0]] for pt in points]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "element_type": "contour_line",
                "elevation_m": elevation,
                "color": color,
            }
        })
        self._mark_modified()
        self._set_mode_label("Ready")
        self.statusBar().showMessage(
            f"Contour line at {elevation:.1f}m placed", 2000
        )

    def _on_contour_cleared(self):
        """Clear all contours from map and project."""
        self.map_widget.clear_contours()
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") != "contour_line"
        ]
        self._mark_modified()

    def _on_wind_requested(self, config: dict):
        """A4: Draw wind overlay with shelter zones."""
        self.map_widget.draw_wind_overlay(config)
        self._set_mode_label(
            f"Wind from {config.get('direction_from', '?')}° ({config.get('speed_label', '')})"
        )

    def _enter_guild_mode(self, guild_data: dict):
        """Place a guild on the map — click to place centre."""
        self._current_mode = 'guild'
        self._pending_guild = guild_data
        self.map_widget.run_js("map.getContainer().style.cursor = 'crosshair';")
        self._set_mode_label(
            f"Placing guild: {guild_data.get('name', '?')} — click map to place centre"
        )
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_guild_click)
        except TypeError:
            pass
        self.map_widget.bridge.map_clicked.connect(self._on_guild_click)

    def _on_guild_click(self, lat: float, lng: float):
        """Handle map click while in guild placement mode."""
        if self._current_mode != 'guild' or not hasattr(self, '_pending_guild'):
            return
        import json as _json
        import math

        guild = self._pending_guild
        members = guild.get("members", [])

        # Enrich member data with spacing/height for the JS visualisation
        enriched_members = []
        for m in members:
            spacing_m, plant_type, _ = self._plant_info(m["plant_id"])
            try:
                from src.db.plants import get_plant
                p = get_plant(m["plant_id"])
                height = float(p.get("mature_height_meters") or 1.0) if p else 1.0
            except Exception:
                height = 1.0
            enriched_members.append({
                "plant_id": m["plant_id"],
                "common_name": m["common_name"],
                "plant_type": plant_type,
                "role": m.get("role", "other"),
                "offset_x": m.get("offset_x", 0),
                "offset_y": m.get("offset_y", 0),
                "spacing_meters": spacing_m,
                "mature_height_meters": height,
            })

        guild_js = {
            "name": guild.get("name", "Guild"),
            "members": enriched_members,
        }

        # Call JS placeGuildOnMap for visual rendering
        js_data = _json.dumps(guild_js).replace("'", "\\'")
        self.map_widget.run_js(
            f"placeGuildOnMap(JSON.parse('{js_data}'), {lat}, {lng});"
        )

        # Track each member in project state
        for m in enriched_members:
            lat_offset = (m["offset_y"]) / 111320
            lng_offset = (m["offset_x"]) / (111320 * math.cos(lat * math.pi / 180))
            mlat = lat + lat_offset
            mlng = lng + lng_offset

            self._placed_plants.append({
                "plant_id": m["plant_id"], "common_name": m["common_name"],
                "lat": mlat, "lng": mlng
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [mlng, mlat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": m["plant_id"],
                    "common_name": m["common_name"],
                    "guild_name": guild.get("name", ""),
                    "quantity": 1
                }
            })
            self.plant_panel.on_plant_placed(m["plant_id"], m["common_name"])

        self._mark_modified()
        self._cancel_draw()
        try:
            self.map_widget.bridge.map_clicked.disconnect(self._on_guild_click)
        except TypeError:
            pass
        self.statusBar().showMessage(
            f"Placed guild '{guild.get('name', '')}' with {len(enriched_members)} members", 3000
        )

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

        self._mark_modified()
        self.toolbar.reset_draw_buttons()
        self._set_mode_label("Boundary set — " + zone_label(self._current_zone))

    def _on_plant_placed(self, plant_id: int, common_name: str, lat: float, lng: float):
        self._push_undo({
            "action": "place_plant",
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
        })
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
        self._mark_modified()

    def _on_plant_removed(self, marker_id: str, plant_id: int, lat: float, lng: float):
        # Remove matching entry from placed list (match by plant_id + coords)
        for i, p in enumerate(self._placed_plants):
            if (p["plant_id"] == plant_id
                    and abs(p["lat"] - lat) < 1e-7
                    and abs(p["lng"] - lng) < 1e-7):
                self._placed_plants.pop(i)
                break

        # Remove matching feature from project
        removed = False
        kept = []
        for f in self._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (not removed
                    and props.get("element_type") == "plant"
                    and props.get("plant_id") == plant_id
                    and coords
                    and abs(coords[1] - lat) < 1e-7
                    and abs(coords[0] - lng) < 1e-7):
                removed = True
            else:
                kept.append(f)
        self._project["features"] = kept

        self.plant_panel.on_plant_removed(plant_id)
        self._mark_modified()

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
        self._mark_modified()
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
        self.plant_panel.clear_placed()
        self.plant_panel.set_zone(None)
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

        if data["boundary"]:
            self.map_widget.load_boundary(data["boundary"])
            lats = [p[0] for p in data["boundary"]]
            lngs = [p[1] for p in data["boundary"]]
            self._set_zone_display(
                get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs))
            )

        for p in data["plants"]:
            spacing_m, plant_type, custom_color = self._plant_info(p["plant_id"])
            self.map_widget.load_plant_marker(
                p["plant_id"], p["common_name"], p["lat"], p["lng"],
                spacing_m, plant_type, custom_color
            )
            self._placed_plants.append(p)

        self.plant_panel.load_placed(data["plants"])

        if data["zone_center"]:
            self.map_widget.load_zone_center(*data["zone_center"])

        for s in data.get("structures", []):
            self.map_widget.load_structure(s["struct_def"], s["lat"], s["lng"])

        for h in data.get("hedgerows", []):
            self.map_widget.load_hedgerow(h)

        for sh in data.get("shapes", []):
            self.map_widget.load_shape(sh)

        # Contour lines are loaded via JS (finishContour re-uses the drawing logic)
        # We redraw them directly as polylines
        for ctr in data.get("contours", []):
            import json as _json
            ctr_js = _json.dumps(ctr).replace("'", "\\'")
            self.map_widget.run_js(
                f"(function() {{"
                f"  var d = JSON.parse('{ctr_js}');"
                f"  contourPoints = d.points;"
                f"  currentContour = d;"
                f"  finishContour();"
                f"  contourPoints = [];"
                f"}})()"
            )

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

    # ── Shopping list export ─────────────────────────────────────────────────

    def _on_export_shopping_list(self):
        if not self._placed_plants:
            QMessageBox.information(self, "Shopping List", "No plants placed yet.")
            return

        # Count by plant_id
        from collections import Counter
        counts: Counter = Counter()
        names: dict[int, str] = {}
        for p in self._placed_plants:
            pid = p["plant_id"]
            counts[pid] += 1
            names[pid] = p["common_name"]

        # Build list with type info
        try:
            from src.db.plants import get_plant
            lines = ["PermaDesign — Shopping List", "=" * 40, ""]
            type_groups: dict[str, list[str]] = {}
            total = 0
            for pid, qty in sorted(counts.items(), key=lambda x: names.get(x[0], "")):
                plant = get_plant(pid)
                ptype = plant.get("plant_type", "other") if plant else "other"
                sci = plant.get("scientific_name", "") if plant else ""
                line = f"  {names[pid]}"
                if sci:
                    line += f"  ({sci})"
                line += f"  ×{qty}"
                type_groups.setdefault(ptype, []).append(line)
                total += qty

            type_order = ["tree", "shrub", "herb", "groundcover", "vine", "root"]
            for t in type_order:
                if t in type_groups:
                    lines.append(f"{t.upper()}S")
                    lines.extend(sorted(type_groups[t]))
                    lines.append("")

            lines.append(f"{'=' * 40}")
            lines.append(f"Total: {total} plants ({len(counts)} species)")
        except Exception:
            lines = [f"{names.get(pid, '?')}  ×{qty}" for pid, qty in counts.items()]

        text = "\n".join(lines)

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Shopping List", "shopping_list.txt",
            "Text Files (*.txt);;CSV (*.csv);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.statusBar().showMessage(f"Shopping list saved: {path}", 3000)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    # ── Undo / Redo ────────────────────────────────────────────────────────

    def _push_undo(self, entry: dict):
        self._undo_stack.append(entry)
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._act_undo.setEnabled(True)
        self._act_redo.setEnabled(False)

    def _do_undo(self):
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        action = entry["action"]

        if action == "place_plant":
            # Remove the most recent marker matching this plant + coords
            pid, lat, lng = entry["plant_id"], entry["lat"], entry["lng"]
            self.map_widget.run_js(
                f"(function() {{"
                f"  var keys = Object.keys(plantMarkers);"
                f"  for (var i = keys.length - 1; i >= 0; i--) {{"
                f"    var m = plantMarkers[keys[i]];"
                f"    if (m._pd && m._pd.plantId === {pid}"
                f"        && Math.abs(m._pd.lat - {lat}) < 1e-7"
                f"        && Math.abs(m._pd.lng - {lng}) < 1e-7) {{"
                f"      map.removeLayer(m);"
                f"      if (plantLabels[keys[i]]) {{ map.removeLayer(plantLabels[keys[i]]); delete plantLabels[keys[i]]; }}"
                f"      delete plantMarkers[keys[i]];"
                f"      break;"
                f"    }}"
                f"  }}"
                f"}})()"
            )
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
        elif key == Qt.Key.Key_B and not event.modifiers():
            self._enter_boundary_mode()
        elif key == Qt.Key.Key_P and not event.modifiers():
            # Switch to Plants tab
            self._side_tabs.setCurrentWidget(self.plant_panel)
        elif key == Qt.Key.Key_G and not event.modifiers():
            # Switch to Guilds tab
            self._side_tabs.setCurrentWidget(self.guild_panel)
        elif key == Qt.Key.Key_S and not event.modifiers():
            # Switch to Structures tab
            self._side_tabs.setCurrentWidget(self.structure_panel)
        elif key == Qt.Key.Key_A and not event.modifiers():
            # Switch to Analysis tab
            self._side_tabs.setCurrentWidget(self.analysis_panel)
        elif key == Qt.Key.Key_M and not event.modifiers():
            self._enter_measure_mode()
        elif key == Qt.Key.Key_Z and not event.modifiers():
            self._enter_zone_mode()
        elif key == Qt.Key.Key_N and not event.modifiers():
            self._enter_annotate_mode()
        elif key == Qt.Key.Key_L and not event.modifiers():
            # Toggle map legend
            self.map_widget.run_js("toggleLegend();")
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
