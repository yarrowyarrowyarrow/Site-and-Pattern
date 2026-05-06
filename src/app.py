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
from src.planning_panel   import PlanningPanel
from src.toolbar          import MainToolbar
from src.climate          import get_zone, zone_label
from src.settings         import SettingsDialog, get_api_keys
from src.collapsible_panel import CollapsibleSidebar
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

        # Pending anchor-mode configs (set when entering anchor mode, cleared after render)
        self._pending_sun_config:    dict | None = None
        self._pending_sun_anchor:    tuple | None = None
        self._pending_sector_config: dict | None = None

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
        self.planning_panel  = PlanningPanel(self)

        # Tabbed side panel
        self._side_tabs = QTabWidget()
        self._side_tabs.addTab(self.plant_panel, "Plants")
        self._side_tabs.addTab(self.guild_panel, "Guilds")
        self._side_tabs.addTab(self.structure_panel, "Structures")
        self._side_tabs.addTab(self.analysis_panel, "Analysis")
        self._side_tabs.addTab(self.planning_panel, "Planning")
        self._side_tabs.setMinimumWidth(220)
        self._side_tabs.setMaximumWidth(480)
        self._side_tabs.setStyleSheet(
            "QWidget { background-color: #1e2a1e; color: #c8e6c9; }"
        )

        # Wrap in a CollapsibleSidebar so the entire side panel can be
        # collapsed to a thin chevron strip — replaces the long-standing
        # workaround of "minimize the Design panel" via the splitter.
        self._side_wrapper = CollapsibleSidebar(
            "Side Panel", panel_id="main_sidebar", expanded=True
        )
        self._side_wrapper.set_content(self._side_tabs)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.map_widget)
        splitter.addWidget(self._side_wrapper)

        # 70 / 30 split
        splitter.setSizes([700, 300])
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

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

        act_pdf = file_menu.addAction("Export &PDF…")
        act_pdf.setStatusTip("Export design as a presentation-quality PDF")
        act_pdf.triggered.connect(self._on_export_pdf)

        file_menu.addSeparator()

        act_exit = file_menu.addAction("E&xit")
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(self.close)

    # ── Signal wiring ─────────────────────────────────────────────────────────

    def _connect_signals(self):
        b = self.map_widget.bridge

        # Map → status bar
        b.mouse_moved.connect(self._on_mouse_moved)

        # Map events → project state (boundary_complete re-connected below with new signature)
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

        # Toolbar → clear measure
        self.toolbar.measure_cleared.connect(self.map_widget.clear_measure)

        # Analysis panel → map (A1-A4)
        self.analysis_panel.sun_path_requested.connect(self._on_sun_path_requested)
        self.analysis_panel.sun_path_cleared.connect(self.map_widget.clear_sun_path)
        self.analysis_panel.sector_requested.connect(self._on_sector_requested)
        self.analysis_panel.sector_cleared.connect(self.map_widget.clear_sectors)
        self.analysis_panel.contour_requested.connect(self._on_contour_requested)
        self.analysis_panel.contour_cleared.connect(self._on_contour_cleared)
        self.analysis_panel.terrain_requested.connect(self._on_terrain_requested)
        self.analysis_panel.wind_requested.connect(self._on_wind_requested)
        self.analysis_panel.wind_cleared.connect(self.map_widget.clear_wind_overlay)
        self.analysis_panel.season_changed.connect(self._on_season_changed)

        # Map → guild removal
        b.guild_removed.connect(self._on_guild_removed)

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
                          quantity: int = 1, pattern: dict | None = None):
        self._current_mode = 'plant'
        spacing_m, plant_type, custom_color = self._plant_info(plant_id)

        # Polyculture override: when the panel built a mix recipe, use
        # the resolved effective spacing (default = max canopy width)
        # so the JS-side geometry generator lays out cells at a step
        # that fits the largest species in the mix.
        poly = ((pattern or {}).get("params") or {}).get("polyculture")
        if poly and poly.get("effective_spacing_m"):
            spacing_m = float(poly["effective_spacing_m"])

        self.map_widget.set_mode('plant', plant_id, common_name, spacing_m,
                                 plant_type, quantity, custom_color,
                                 pattern=pattern)
        self.toolbar.enter_plant_mode()

        kind = (pattern or {}).get("kind", "single")
        species_n = len(poly["species"]) if poly else 0
        poly_tag = f" · Polyculture ({species_n} species)" if species_n else ""
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
        self._sync_planning_panel()

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
        """A1: Enter anchor-placement mode; render after user clicks the map."""
        self._pending_sun_config = config
        self._pending_sun_anchor = None
        self.map_widget.enter_sun_anchor_mode()
        self._set_mode_label("Click map to place sun path anchor — right-click to cancel")

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
        """A2: Enter anchor-placement mode; draw after user clicks the map."""
        self._pending_sector_config = config
        self.map_widget.enter_sector_anchor_mode()
        self._set_mode_label("Click map to place sector anchor — right-click to cancel")

    def _on_contour_requested(self, config: dict):
        """A3: Enter contour drawing mode."""
        self._current_mode = 'contour'
        self.map_widget.set_contour_mode(config)
        self.toolbar.reset_draw_buttons()
        elev = config.get("elevation_m", 0)
        self._set_mode_label(
            f"Drawing contour at {elev:.1f}m — click points, double-click to finish"
        )

    def _on_contour_complete(self, points_json: str, elevation: float,
                             color: str, source: str = "manual"):
        """Save contour line to project."""
        import json as _json
        points = _json.loads(points_json)
        coords = [[pt[1], pt[0]] for pt in points]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "element_type": "contour_line",
                "elevation_m":  elevation,
                "color":        color,
                "source":       source,
            }
        })
        self._mark_modified()
        if source == "manual":
            self._set_mode_label("Ready")
            self.statusBar().showMessage(
                f"Contour line at {elevation:.1f}m placed", 2000
            )

    def _on_contour_removed(self, points_json: str, elevation: float, color: str):
        """Remove a single contour line from project state."""
        kept = []
        removed = False
        for f in self._project["features"]:
            props = f.get("properties", {})
            if (not removed
                    and props.get("element_type") == "contour_line"
                    and abs(props.get("elevation_m", -1) - elevation) < 0.01):
                removed = True
            else:
                kept.append(f)
        self._project["features"] = kept
        self._mark_modified()
        self.statusBar().showMessage(
            f"Contour line at {elevation:.1f}m removed", 2000
        )

    def _on_contour_cleared(self):
        """Clear all contours from map and project."""
        self.map_widget.clear_contours()
        self._project["features"] = [
            f for f in self._project["features"]
            if f.get("properties", {}).get("element_type") != "contour_line"
        ]
        self._mark_modified()

    # ── Terrain auto-generate ─────────────────────────────────────────────────

    def _project_bbox(self) -> tuple | None:
        """Return (lat_min, lat_max, lng_min, lng_max) with 10% padding, or None."""
        lats, lngs = [], []
        for f in self._project.get("features", []):
            if f.get("properties", {}).get("element_type") == "property_boundary":
                for coord in f.get("geometry", {}).get("coordinates", [[]])[0]:
                    lngs.append(coord[0])
                    lats.append(coord[1])
        if not lats:
            return None
        lat_min, lat_max = min(lats), max(lats)
        lng_min, lng_max = min(lngs), max(lngs)
        # Add ~10% buffer so contours extend slightly beyond the drawn boundary
        lat_pad = (lat_max - lat_min) * 0.10 or 0.001
        lng_pad = (lng_max - lng_min) * 0.10 or 0.001
        return (lat_min - lat_pad, lat_max + lat_pad,
                lng_min - lng_pad, lng_max + lng_pad)

    def _on_terrain_requested(self, interval_m: float, grid_pts: int):
        """Auto-generate contours from real elevation data."""
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QMessageBox
        from src.elevation import ElevationFetchWorker

        bbox = self._project_bbox()
        if bbox is None:
            QMessageBox.warning(
                self, "No Boundary",
                "Draw a property boundary first so the terrain extent is known."
            )
            self.analysis_panel.set_terrain_status("")
            return

        self._pending_interval_m = interval_m

        self._elev_worker = ElevationFetchWorker(bbox, grid_pts, grid_pts)
        self._elev_thread = QThread()
        self._elev_worker.moveToThread(self._elev_thread)
        self._elev_worker.finished.connect(self._on_elevation_ready)
        self._elev_worker.error.connect(self._on_elevation_error)
        self._elev_thread.started.connect(self._elev_worker.run)
        self._elev_worker.finished.connect(self._elev_thread.quit)
        self._elev_worker.error.connect(self._elev_thread.quit)
        self._elev_thread.start()

    def _on_elevation_ready(self, data: dict):
        source   = data.get("source", "unknown")
        from_cache = data.get("_from_cache", False)

        if source == "edmonton_opendata":
            self.map_widget.add_contour_features(data.get("features", []))
            status = "Edmonton LiDAR — cached ✓" if from_cache else "Edmonton LiDAR — fetched ✓"
        else:
            self.map_widget.generate_contours_from_grid(
                data, self._pending_interval_m
            )
            label = "cached ✓" if from_cache else "fetched ✓"
            if data.get("_fallback_reason"):
                status = f"SRTM fallback — {label}"
            else:
                status = f"SRTM 30m — {label}"

        self.analysis_panel.set_terrain_status(status)

    def _on_elevation_error(self, message: str):
        from PyQt6.QtWidgets import QMessageBox
        self.analysis_panel.set_terrain_status(f"Error — see message")
        QMessageBox.information(
            self, "Terrain Data Unavailable",
            f"Could not fetch elevation data:\n\n{message}\n\n"
            "You can still draw contour lines manually."
        )

    def _on_wind_requested(self, config: dict):
        """A4: Draw wind overlay with shelter zones."""
        self.map_widget.draw_wind_overlay(config)
        self._set_mode_label(
            f"Wind from {config.get('direction_from', '?')}° ({config.get('speed_label', '')})"
        )

    def _on_season_changed(self, season: str):
        """Apply seasonal view to the map — adjusts plant visibility by type."""
        import json as _json
        from src.db.plants import get_plant

        # Seasonal opacity rules based on deciduous_evergreen field
        # Summer: everything full
        # Winter: deciduous → 0.15, herbaceous → 0.05, evergreen → 1.0
        # Spring/Fall: intermediate
        season_opacity = {
            "Summer":  {"deciduous": 1.0, "evergreen": 1.0, "herbaceous": 1.0},
            "Spring":  {"deciduous": 0.7, "evergreen": 1.0, "herbaceous": 0.6},
            "Fall":    {"deciduous": 0.5, "evergreen": 1.0, "herbaceous": 0.4},
            "Winter":  {"deciduous": 0.15, "evergreen": 1.0, "herbaceous": 0.05},
        }
        rules = season_opacity.get(season, season_opacity["Summer"])

        pid_vis = {}
        plant_cache = {}
        for p in self._placed_plants:
            pid = p["plant_id"]
            if pid not in plant_cache:
                plant = get_plant(pid)
                if plant:
                    de = (plant.get("deciduous_evergreen") or "").lower()
                    if de in ("evergreen",):
                        plant_cache[pid] = "evergreen"
                    elif de in ("deciduous",):
                        plant_cache[pid] = "deciduous"
                    else:
                        # Herbs, groundcover, etc. treated as herbaceous
                        ptype = plant.get("plant_type", "herb")
                        if ptype in ("tree", "shrub"):
                            plant_cache[pid] = "deciduous"
                        else:
                            plant_cache[pid] = "herbaceous"
                else:
                    plant_cache[pid] = "herbaceous"

            pid_vis[pid] = rules[plant_cache[pid]]

        js_data = _json.dumps(pid_vis)
        self.map_widget.run_js(f"setSeasonView('{season}', {js_data});")
        self._set_mode_label(f"Season: {season}")

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
        self.map_widget.run_js(
            f"placeGuildOnMap(JSON.parse({_json.dumps(_json.dumps(guild_js))}), {lat}, {lng});"
        )

        # All members of one guild placement share a single placement group.
        group_id = project_io.new_placement_group_id()

        # Track each member in project state
        for m in enriched_members:
            lat_offset = (m["offset_y"]) / 111320
            lng_offset = (m["offset_x"]) / (111320 * math.cos(lat * math.pi / 180))
            mlat = lat + lat_offset
            mlng = lng + lng_offset

            self._placed_plants.append({
                "plant_id": m["plant_id"], "common_name": m["common_name"],
                "lat": mlat, "lng": mlng,
                "guild_name": guild.get("name", ""),
                "guild_center_lat": lat, "guild_center_lng": lng,
                "placement_group_id": group_id,
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [mlng, mlat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": m["plant_id"],
                    "common_name": m["common_name"],
                    "guild_name": guild.get("name", ""),
                    "guild_center_lat": lat,
                    "guild_center_lng": lng,
                    "placement_group_id": group_id,
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
        # Drop any in-flight polyculture recipe — the user explicitly
        # exited plant mode, so the next Place Mix click should re-stash
        # a fresh one.
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass

    # ── Map event handlers ────────────────────────────────────────────────────

    def _on_boundary_complete(self, bid: str, coords: list, color: str):
        """Multi-boundary: add a new boundary to the project."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {
                "element_type": "property_boundary",
                "boundary_id": bid,
                "color": color,
                "show_lengths": True,
                "show_area": True,
            }
        })

        lats = [pt[0] for pt in coords]
        lngs = [pt[1] for pt in coords]
        self._set_zone_display(get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs)))

        self._mark_modified()
        self.toolbar.reset_draw_buttons()
        self._set_mode_label(
            f"Boundary added ({color}) — " + zone_label(self._current_zone)
        )

    def _on_boundary_geom_changed(self, bid: str, coords: list):
        """Update geometry of an existing boundary after vertex/move/scale drag."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        for f in self._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["geometry"]["coordinates"] = [ring]
                break
        self._mark_modified()

    def _on_boundary_props_changed(self, bid: str, color: str,
                                    show_lengths: bool, show_area: bool):
        """Update color/label toggles for an existing boundary."""
        for f in self._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["properties"]["color"] = color
                f["properties"]["show_lengths"] = show_lengths
                f["properties"]["show_area"] = show_area
                break
        self._mark_modified()

    def _on_boundary_removed(self, bid: str):
        """Remove a boundary from the project."""
        self._project["features"] = [
            f for f in self._project["features"]
            if not (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid)
        ]
        self._mark_modified()

    def _on_sun_anchor_placed(self, lat: float, lng: float):
        """User placed sun-path anchor; now compute and draw."""
        self._pending_sun_anchor = (lat, lng)
        if self._pending_sun_config:
            self._render_sun_path(self._pending_sun_config, lat, lng)

    def _on_sector_anchor_placed(self, lat: float, lng: float):
        """User placed sector anchor; now draw."""
        if self._pending_sector_config:
            self.map_widget.draw_sectors(self._pending_sector_config, lat, lng)
            names = [s["name"] for s in self._pending_sector_config.get("sectors", [])]
            self._set_mode_label(f"Sectors: {', '.join(names)}")
            self._pending_sector_config = None

    def _on_sun_path_removed(self):
        self._set_mode_label("Sun path removed")

    def _on_anchor_cancelled(self, mode: str):
        self.toolbar.reset_draw_buttons()
        self._set_mode_label("Ready")
        try:
            self.plant_panel.clear_pending_polyculture()
        except Exception:
            pass

    def _on_sector_group_removed(self, sid: str):
        self._set_mode_label("Sector group removed")

    def _on_sector_group_moved(self, sid: str, lat: float, lng: float):
        pass  # could persist if sectors were saved to project file

    def _on_sector_group_rotated(self, sid: str, rotation_deg: float):
        pass

    def _on_sector_group_resized(self, sid: str, radius_m: float):
        pass

    def _on_plant_placed(self, plant_id: int, common_name: str, lat: float, lng: float):
        # Single-click placement: each plant gets its own singleton group.
        group_id = project_io.new_placement_group_id()
        self._push_undo({
            "action": "place_plant",
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
            "placement_group_id": group_id,
        })
        self._placed_plants.append({
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
            "placement_group_id": group_id,
        })
        self._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "plant",
                "plant_id": plant_id,
                "common_name": common_name,
                "placement_group_id": group_id,
                "quantity": 1
            }
        })
        # Tell JS the marker's group id so right-click → "Delete group" works.
        self.map_widget.run_js(
            f"setPlantGroupForLatest({plant_id}, {lat}, {lng}, "
            f"{repr(group_id)});"
        )
        self.plant_panel.on_plant_placed(plant_id, common_name)
        self._mark_modified()
        self._sync_planning_panel()

    def _on_pattern_placed(self, plant_id: int, common_name: str, spacing_m: float,
                            plant_type: str, custom_color: str,
                            positions_json: str, pattern_kind: str):
        """Place N plants at once (Burst, Row, Grid, Circle).

        All plants share a single placement_group_id so they can be selected
        and deleted as a unit. The positions list is computed JS-side so the
        live preview and the committed placement use the same geometry.

        When the plant panel's polyculture mix had ≥2 species at the time
        Place was clicked, the panel stashed a recipe; we consume it here
        and assign one species per generated position. Each placed marker
        carries its own plant_id/common_name/colour, but the whole stand
        still shares one placement_group_id so it selects and deletes
        as a single polyculture.
        """
        import json as _json
        try:
            positions = _json.loads(positions_json)
        except Exception:
            return
        if not positions:
            return

        # Peek (don't consume) the polyculture recipe stashed at
        # Place-click time. Keeping it alive lets the user drop multiple
        # back-to-back patterns without re-clicking Place Mix; it's
        # only cleared when plant mode is exited (Esc / cancel) or the
        # user clicks Place Mix again with a different mix.
        assignments: list[dict] | None = None
        poly = None
        try:
            poly = self.plant_panel.peek_pending_polyculture()
        except Exception:
            poly = None
        if poly and len(poly.get("species", [])) >= 2:
            from src.polyculture import assign_species, optimize_layout
            assignments = assign_species(
                positions, poly["species"], poly.get("strategy", "even_split")
            )
            # Now permute that ratio-correct assignment so same-species
            # plants are spread as far apart as the geometry allows.
            # The optimiser only swaps pairs, so per-species counts
            # (the user's ratios) are preserved exactly.
            try:
                assignments = optimize_layout(positions, assignments)
            except Exception:
                # Fall back to the un-optimised but ratio-correct list
                # if SA blows up; better to plant clumped than to crash.
                pass

        group_id = project_io.new_placement_group_id()
        for i, (lat, lng) in enumerate(positions):
            if assignments is not None:
                sp = assignments[i]
                pid       = sp["id"]
                name      = sp["common_name"]
                sp_space  = sp["spacing_m"]
                sp_type   = sp["plant_type"]
                sp_color  = sp["color"]
            else:
                pid, name           = plant_id, common_name
                sp_space, sp_type   = spacing_m, plant_type
                sp_color            = custom_color

            # Render the marker on the map.
            self.map_widget.run_js(
                f"placePlantMarker({pid}, {repr(name)}, "
                f"{lat}, {lng}, {sp_space}, {repr(sp_type)}, "
                f"{repr(sp_color) if sp_color else 'null'}, "
                f"{repr(group_id)});"
            )
            # Mirror in project state.
            self._placed_plants.append({
                "plant_id": pid, "common_name": name,
                "lat": lat, "lng": lng,
                "placement_group_id": group_id,
            })
            self._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "placement_group_id": group_id,
                    "pattern_kind": pattern_kind,
                    "quantity": 1
                }
            })
            self.plant_panel.on_plant_placed(pid, name)
        self._mark_modified()
        self._sync_planning_panel()
        if assignments is not None:
            n_species = len({s["id"] for s in poly["species"]})
            self.statusBar().showMessage(
                f"Placed {len(positions)} plants — "
                f"{n_species}-species polyculture ({pattern_kind})", 3000
            )
            # Persist the "click again to drop another" hint in the
            # mode label since the recipe stays armed until Esc.
            self._set_mode_label(
                f"Placed polyculture ({pattern_kind}). Click again for another, "
                f"or press Esc to finish."
            )
        else:
            self.statusBar().showMessage(
                f"Placed {len(positions)} {common_name} ({pattern_kind})", 2500
            )

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
        self._sync_planning_panel()

    def _on_guild_removed(self, guild_name: str, center_lat: float, center_lng: float):
        """Remove all guild member plant features from project state.

        Members are identified by the guild_center_{lat,lng} anchor they were
        tagged with at placement time — the previous approach of matching
        each plant's own coordinate against the center with a 0.001-degree
        (~111 m) tolerance both missed members farther than 100 m from the
        center and could match plants from adjacent guilds with identical
        names.
        """
        # 1e-7 deg ≈ 1 cm — plenty tight while absorbing float round-trip noise.
        TOL = 1e-7

        def _anchors_match(anchor_lat, anchor_lng):
            if anchor_lat is None or anchor_lng is None:
                return False
            return (abs(anchor_lat - center_lat) < TOL
                    and abs(anchor_lng - center_lng) < TOL)

        kept_plants = []
        for p in self._placed_plants:
            if (p.get("guild_name") == guild_name
                    and _anchors_match(p.get("guild_center_lat"),
                                       p.get("guild_center_lng"))):
                continue  # drop this guild member
            kept_plants.append(p)
        removed_count = len(self._placed_plants) - len(kept_plants)
        self._placed_plants = kept_plants

        kept_features = []
        for f in self._project["features"]:
            props = f.get("properties", {})
            if (props.get("element_type") == "plant"
                    and props.get("guild_name") == guild_name
                    and _anchors_match(props.get("guild_center_lat"),
                                       props.get("guild_center_lng"))):
                continue  # drop this guild member
            kept_features.append(f)
        self._project["features"] = kept_features

        # Update plant panel counts
        for _ in range(removed_count):
            self.plant_panel.on_plant_removed(0)
        self._mark_modified()
        self._sync_planning_panel()

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
        self.planning_panel.set_notes("")
        self.planning_panel.set_placed_plants([])
        self.planning_panel.set_structures([])
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
            self.map_widget.load_plant_marker(
                p["plant_id"], p["common_name"], p["lat"], p["lng"],
                spacing_m, plant_type, custom_color,
                p.get("placement_group_id", "")
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
            self.map_widget.run_js(
                f"(function() {{"
                f"  var d = JSON.parse({_json.dumps(_json.dumps(ctr))});"
                f"  contourPoints = d.points;"
                f"  currentContour = d;"
                f"  finishContour();"
                f"  contourPoints = [];"
                f"}})()"
            )

        # Load notes
        notes = proj.get("properties", {}).get("notes", "")
        self.planning_panel.set_notes(notes)

        name = proj.get("properties", {}).get("project_name", "Design")
        self.setWindowTitle(f"PermaDesign — {name}")

        self._sync_planning_panel()

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
        self._project["properties"]["notes"] = text
        self._mark_modified()

    # ── Timeline / succession ──────────────────────────────────────────────

    def _on_timeline_year_changed(self, year: int):
        """Compute per-plant scale factors for the timeline year and send to JS."""
        import json as _json
        import math

        from src.db.plants import get_plant

        _DEFAULT_YTM = {"tree": 15, "shrub": 5, "herb": 2, "groundcover": 1, "vine": 2, "root": 2}

        scale_data = []
        # Build a mapping from markerId patterns to placed plants
        # MarkerIds follow pattern: {plantId}_{timestamp}_{random}
        # We need to iterate plantMarkers in JS, so we build scale data keyed by markerIds
        # Since we don't have JS markerIds in Python, we build per-plant-id scale factors
        # and let JS match by plantId
        plant_cache = {}  # plant_id -> (ytm, curve)
        summary_trees = 0
        summary_mature = 0
        summary_total = len(self._placed_plants)

        for p in self._placed_plants:
            pid = p["plant_id"]
            if pid not in plant_cache:
                plant = get_plant(pid)
                if plant:
                    ytm = plant.get("years_to_maturity") or _DEFAULT_YTM.get(
                        plant.get("plant_type", "herb"), 2)
                    curve = plant.get("growth_curve") or "steady"
                    ptype = plant.get("plant_type", "herb")
                else:
                    ytm = 2
                    curve = "steady"
                    ptype = "herb"
                plant_cache[pid] = (ytm, curve, ptype)

            ytm, curve, ptype = plant_cache[pid]

            if year == 0:
                factor = 1.0
            elif year >= ytm:
                factor = 1.0
            else:
                ratio = year / ytm
                if curve == "fast_early":
                    factor = math.sqrt(ratio)
                elif curve == "slow_start":
                    factor = ratio ** 1.5
                else:  # steady
                    factor = ratio
            factor = max(0.1, min(1.0, factor))

            if ptype == "tree":
                summary_trees += 1
            if factor >= 0.95:
                summary_mature += 1

        # Build summary text
        if year == 0:
            summary = "Planting day — all plants at initial size."
        else:
            pct_mature = int(summary_mature / max(1, summary_total) * 100)
            summary = (
                f"Year {year}: {summary_mature}/{summary_total} plants at maturity "
                f"({pct_mature}%)."
            )
            if summary_trees > 0:
                # Find avg tree scale
                tree_scales = []
                for p in self._placed_plants:
                    pid = p["plant_id"]
                    ytm, curve, ptype = plant_cache[pid]
                    if ptype == "tree":
                        ratio = min(1.0, year / ytm)
                        if curve == "fast_early":
                            tree_scales.append(math.sqrt(ratio))
                        elif curve == "slow_start":
                            tree_scales.append(ratio ** 1.5)
                        else:
                            tree_scales.append(ratio)
                avg_tree = sum(tree_scales) / len(tree_scales) if tree_scales else 0
                summary += f"\nTrees: ~{int(avg_tree * 100)}% of mature canopy."

        self.planning_panel.update_timeline_summary(summary)

        # Send scale data to JS — we use a per-plantId approach
        # JS will iterate plantMarkers and look up scaleFactor by plantId
        pid_factors = {}
        for pid, (ytm, curve, ptype) in plant_cache.items():
            if year == 0:
                factor = 1.0
            elif year >= ytm:
                factor = 1.0
            else:
                ratio = year / ytm
                if curve == "fast_early":
                    factor = math.sqrt(ratio)
                elif curve == "slow_start":
                    factor = ratio ** 1.5
                else:
                    factor = ratio
            pid_factors[pid] = max(0.1, min(1.0, factor))

        js_data = _json.dumps(pid_factors)
        self.map_widget.run_js(f"setTimelineYearByPlantId({year}, {js_data});")

    # ── Planning panel sync ──────────────────────────────────────────────

    def _sync_planning_panel(self):
        """Push current placed plants and structures to the planning panel."""
        enriched = []
        for p in self._placed_plants:
            entry = dict(p)
            try:
                from src.db.plants import get_plant
                plant_data = get_plant(p["plant_id"])
                if plant_data:
                    entry["plant_type"] = plant_data.get("plant_type", "herb")
                    entry["water_needs"] = plant_data.get("water_needs", "medium")
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
            self.map_widget.run_js("clearSelection();")
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            # Delete every currently-selected map item (across types).
            self.map_widget.run_js("deleteSelected();")
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
        elif key == Qt.Key.Key_T and not event.modifiers():
            # Switch to Planning tab
            self._side_tabs.setCurrentWidget(self.planning_panel)
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
