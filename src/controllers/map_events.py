"""
src/controllers/map_events.py — MapBridge → MainWindow event router.

Owns the ``_on_*`` slot handlers wired to MapBridge signals in
``_connect_signals``. These handlers translate user gestures on the
Leaflet map (boundary draws, plant moves, structure placements, …)
into mutations on ``MainWindow._project["features"]`` plus undo-stack
entries, modified-flag updates, and status-bar / mode-label feedback.

Extracted from ``src/app.py:MainWindow`` in Chunk 5d of the
strengthening roadmap. This pilot covers the *boundary* handler family
only — the rest of the ~50 ``_on_*`` handlers (structure, hedgerow,
shape, contour, terrain, sun/sector/wind, plant move/group-move,
polyculture, sun/sector anchor) move in follow-up commits that group
them by feature domain.

Why one-domain-at-a-time:

- The Chunk 4 fallout taught us that touching scattered, deeply-coupled
  code in one big move risks runtime regressions that no static check
  catches. Boundary handlers are the smallest, most self-contained
  domain, so they're the right pilot.
- The shim pattern (``MainWindow._on_X`` → ``self._map_events._on_X``)
  preserves the QSignal.connect() wiring in ``_connect_signals``
  unchanged, so a domain extraction can't accidentally break the
  signal hookup.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QInputDialog

from src.climate import get_zone, zone_label


class MapEventRouter:
    """MapBridge slot handlers. Holds a MainWindow reference so handlers
    can mutate ``_project["features"]`` and call back into the other
    controllers (``_push_undo`` → PersistenceController,
    ``_mark_modified`` → PersistenceController, ``_set_mode_label`` →
    ModeController, ``_set_zone_display`` → MainWindow native).
    """

    def __init__(self, main_window):
        self._main = main_window

    # ── Boundary handlers ────────────────────────────────────────────────────

    def _on_boundary_complete(self, bid: str, coords: list, color: str):
        """Multi-boundary: add a new boundary to the project."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        self._main._project["features"].append({
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
        self._main._set_zone_display(get_zone(sum(lats)/len(lats), sum(lngs)/len(lngs)))

        self._main._push_undo({
            "action": "place_boundary",
            "boundary_id": bid,
            "coords": list(coords),
            "color": color,
        })

        self._main._mark_modified()
        self._main.toolbar.reset_draw_buttons()
        self._main._set_mode_label(
            f"Boundary added ({color}) — " + zone_label(self._main._current_zone)
        )

    def _on_boundary_geom_changed(self, bid: str, coords: list):
        """Update geometry of an existing boundary after vertex/move/scale drag."""
        ring = [[pt[1], pt[0]] for pt in coords] + [[coords[0][1], coords[0][0]]]
        for f in self._main._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["geometry"]["coordinates"] = [ring]
                break
        self._main._mark_modified()

    def _on_boundary_props_changed(self, bid: str, color: str,
                                    show_lengths: bool, show_area: bool):
        """Update color/label toggles for an existing boundary."""
        for f in self._main._project.get("features", []):
            if (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid):
                f["properties"]["color"] = color
                f["properties"]["show_lengths"] = show_lengths
                f["properties"]["show_area"] = show_area
                break
        self._main._mark_modified()

    def _on_boundary_removed(self, bid: str):
        """Remove a boundary from the project."""
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if not (f.get("properties", {}).get("element_type") == "property_boundary"
                    and f["properties"].get("boundary_id") == bid)
        ]
        self._main._mark_modified()

    # ── Structure handlers ───────────────────────────────────────────────────

    def _on_structure_placed(self, struct_id: str, name: str, lat: float,
                              lng: float, size_m: float):
        from src.db.structures import get_structure
        struct_def = get_structure(struct_id)
        if struct_def:
            struct_def = dict(struct_def)
            struct_def["size_m"] = size_m
        else:
            struct_def = {"id": struct_id, "name": name, "size_m": size_m}

        self._main._project["features"].append({
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
        self._main._push_undo({
            "action": "place_structure",
            "struct_id": struct_id,
            "name": name,
            "lat": lat,
            "lng": lng,
            "size_m": size_m,
            "struct_def": struct_def,
        })
        self._main._mark_modified()
        self._main.statusBar().showMessage(f"Placed {name}", 2000)
        self._main._sync_planning_panel()

    def _on_structure_removed(self, marker_id: str, struct_id: str,
                               lat: float, lng: float):
        kept = []
        removed = False
        for f in self._main._project["features"]:
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
        self._main._project["features"] = kept
        self._main._mark_modified()

    # ── Hedgerow handlers ────────────────────────────────────────────────────

    def _on_hedgerow_complete(self, hedge_id: str, points_json: str,
                               species: str, style: str, length_m: float,
                               num_plants: int):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON LineString (lng, lat order)
        coords = [[pt[1], pt[0]] for pt in points]
        self._main._project["features"].append({
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
        self._main._push_undo({
            "action": "place_hedgerow",
            "hedge_id": hedge_id,
            "length_m": length_m,
        })
        self._main._mark_modified()
        self._main._set_mode_label("Ready")
        self._main.statusBar().showMessage(
            f"Hedgerow placed: {length_m:.1f}m, ~{num_plants} plants", 3000
        )

    def _on_hedgerow_removed(self, hedge_id: str, points_json: str):
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if f.get("properties", {}).get("hedge_id") != hedge_id
        ]
        self._main._mark_modified()

    # ── Shape handlers ───────────────────────────────────────────────────────

    def _on_shape_complete(self, shape_id: str, points_json: str, label: str,
                            shape_type: str, fill_color: str, stroke_color: str,
                            fill_opacity: float, dash_array: str, area_m2: float):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON Polygon (lng, lat; closed ring)
        ring = [[pt[1], pt[0]] for pt in points]
        ring.append(ring[0])  # close the ring
        self._main._project["features"].append({
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
        self._main._push_undo({
            "action": "place_custom_shape",
            "shape_id": shape_id,
            "label": label,
            "shape_type": shape_type,
        })
        self._main._mark_modified()
        self._main._set_mode_label("Ready")
        area_str = f"{area_m2:.1f} m²" if area_m2 < 10000 else f"{area_m2/10000:.2f} ha"
        self._main.statusBar().showMessage(
            f"Shape placed: {label or shape_type} ({area_str})", 3000
        )

    def _on_shape_removed(self, shape_id: str):
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if f.get("properties", {}).get("shape_id") != shape_id
        ]
        self._main._mark_modified()

    # ── Contour handlers ─────────────────────────────────────────────────────

    def _on_contour_complete(self, points_json: str, elevation: float,
                              color: str):
        """Save contour line to project."""
        import json as _json
        points = _json.loads(points_json)
        coords = [[pt[1], pt[0]] for pt in points]
        self._main._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "element_type": "contour_line",
                "elevation_m": elevation,
                "color": color,
            }
        })
        self._main._push_undo({
            "action": "place_contour",
            "points": list(points),
            "elevation_m": elevation,
            "color": color,
        })
        self._main._mark_modified()
        self._main._set_mode_label("Ready")
        self._main.statusBar().showMessage(
            f"Contour line at {elevation:.1f}m placed", 2000
        )

    def _on_contour_removed(self, points_json: str, elevation: float,
                             color: str):
        """Remove a single contour line from project state."""
        kept = []
        removed = False
        for f in self._main._project["features"]:
            props = f.get("properties", {})
            if (not removed
                    and props.get("element_type") == "contour_line"
                    and abs(props.get("elevation_m", -1) - elevation) < 0.01):
                removed = True
            else:
                kept.append(f)
        self._main._project["features"] = kept
        self._main._mark_modified()
        self._main.statusBar().showMessage(
            f"Contour line at {elevation:.1f}m removed", 2000
        )

    def _on_contour_cleared(self):
        """Clear all contours from map and project."""
        self._main.map_widget.clear_contours()
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if f.get("properties", {}).get("element_type") != "contour_line"
        ]
        self._main._mark_modified()

    # ── Annotation handlers ──────────────────────────────────────────────────

    def _on_annotate_requested(self, lat: float, lng: float):
        text, ok = QInputDialog.getText(
            self._main, "Add Note", "Note text:", text=""
        )
        if not ok or not text.strip():
            return
        ann_id = f"ann_{int(lat*1e6)}_{int(lng*1e6)}_{id(self._main)}"
        self._main.map_widget.place_annotation(ann_id, lat, lng, text.strip())
        # Save to project
        self._main._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "element_type": "annotation",
                "annotation_id": ann_id,
                "text": text.strip(),
            }
        })
        self._main._mark_modified()

    def _on_annotation_removed(self, ann_id: str):
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if f.get("properties", {}).get("annotation_id") != ann_id
        ]
        self._main._mark_modified()

    # ── Plant move handlers ──────────────────────────────────────────────────

    def _on_plant_moved(self, marker_id: str, plant_id: int,
                        old_lat: float, old_lng: float,
                        new_lat: float, new_lng: float):
        """User dragged a singleton plant marker. Update project state
        and push a single-move undo entry so Ctrl+Z restores the
        previous position."""
        if abs(new_lat - old_lat) < 1e-9 and abs(new_lng - old_lng) < 1e-9:
            return
        # _placed_plants list
        for p in self._main._placed_plants:
            if (p["plant_id"] == plant_id
                    and abs(p["lat"] - old_lat) < 1e-7
                    and abs(p["lng"] - old_lng) < 1e-7):
                p["lat"] = new_lat
                p["lng"] = new_lng
                break
        # Project features
        for f in self._main._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (props.get("element_type") == "plant"
                    and props.get("plant_id") == plant_id
                    and coords
                    and abs(coords[1] - old_lat) < 1e-7
                    and abs(coords[0] - old_lng) < 1e-7):
                f["geometry"]["coordinates"] = [new_lng, new_lat]
                break
        self._main._push_undo({
            "action":   "move_plant",
            "plant_id": plant_id,
            "old_lat":  old_lat, "old_lng": old_lng,
            "new_lat":  new_lat, "new_lng": new_lng,
        })
        self._main._mark_modified()

    def _on_plant_group_moved(self, group_id: str,
                              originals_json: str, moved_json: str):
        """User dragged a polyculture (or other multi-plant) group as
        a cohesive unit. Apply the per-marker delta to project state
        and push a single group-move undo entry."""
        import json as _json
        try:
            originals = _json.loads(originals_json or "[]")
            moved     = _json.loads(moved_json or "[]")
        except Exception:
            return
        if not originals or len(originals) != len(moved):
            return
        # Pair by markerId so updates land on the right feature even if
        # the JSON arrays come back in a different order.
        moved_by_id = {m.get("markerId"): m for m in moved}
        any_change = False
        for orig in originals:
            mid = orig.get("markerId")
            new = moved_by_id.get(mid)
            if not new:
                continue
            old_lat = float(orig.get("lat") or 0.0)
            old_lng = float(orig.get("lng") or 0.0)
            new_lat = float(new.get("lat") or 0.0)
            new_lng = float(new.get("lng") or 0.0)
            if abs(new_lat - old_lat) < 1e-9 and abs(new_lng - old_lng) < 1e-9:
                continue
            any_change = True
            plant_id = orig.get("plantId")
            for p in self._main._placed_plants:
                if (p["plant_id"] == plant_id
                        and abs(p["lat"] - old_lat) < 1e-7
                        and abs(p["lng"] - old_lng) < 1e-7):
                    p["lat"] = new_lat
                    p["lng"] = new_lng
                    break
            for f in self._main._project["features"]:
                props = f.get("properties", {})
                coords = f.get("geometry", {}).get("coordinates", [])
                if (props.get("element_type") == "plant"
                        and props.get("plant_id") == plant_id
                        and props.get("placement_group_id") == group_id
                        and coords
                        and abs(coords[1] - old_lat) < 1e-7
                        and abs(coords[0] - old_lng) < 1e-7):
                    f["geometry"]["coordinates"] = [new_lng, new_lat]
                    break
        if not any_change:
            return
        self._main._push_undo({
            "action":    "move_plant_group",
            "group_id":  group_id,
            "originals": list(originals),
            "moved":     list(moved),
        })
        self._main._mark_modified()
        self._main.statusBar().showMessage(
            f"Moved polyculture group ({len(originals)} plants)", 2000
        )

    # ── Ready / mouse-move ───────────────────────────────────────────────────

    def _on_map_ready(self):
        self._main._set_mode_label("Ready")

    def _on_mouse_moved(self, lat: float, lng: float):
        self._main._sb_coords.setText(f"Lat: {lat:.5f} , Lng: {lng:.5f}")

    # ── Sun-path / sector anchor handlers ───────────────────────────────────

    def _on_sun_anchor_placed(self, lat: float, lng: float):
        """User placed sun-path anchor; now compute and draw."""
        self._main._pending_sun_anchor = (lat, lng)
        if self._main._pending_sun_config:
            self._main._render_sun_path(self._main._pending_sun_config, lat, lng)

    def _on_sector_anchor_placed(self, lat: float, lng: float):
        """User placed sector anchor; now draw."""
        if self._main._pending_sector_config:
            self._main.map_widget.draw_sectors(
                self._main._pending_sector_config, lat, lng,
            )
            names = [s["name"] for s in
                     self._main._pending_sector_config.get("sectors", [])]
            self._main._set_mode_label(f"Sectors: {', '.join(names)}")
            self._main._pending_sector_config = None

    def _on_sun_path_removed(self):
        self._main._set_mode_label("Sun path removed")

    def _on_anchor_cancelled(self, mode: str):
        self._main.toolbar.reset_draw_buttons()
        self._main._set_mode_label("Ready")
        try:
            self._main.plant_panel.clear_pending_polyculture()
        except Exception:
            pass

    def _on_sector_group_removed(self, sid: str):
        self._main._set_mode_label("Sector group removed")

    def _on_sector_group_moved(self, sid: str, lat: float, lng: float):
        pass  # could persist if sectors were saved to project file

    def _on_sector_group_rotated(self, sid: str, rotation_deg: float):
        pass

    def _on_sector_group_resized(self, sid: str, radius_m: float):
        pass

    # ── Site pin handlers ───────────────────────────────────────────────────

    def _on_site_pin_placed(self, lat: float, lng: float, label: str):
        """User dropped a property pin (via search or manual click)."""
        self._main._site_pin_mode = False
        self._main.map_widget.set_site_pin_drop_mode(False)
        self._main.site_panel.set_pin(lat, lng, label)
        # Switch to the Site tab so results are visible.
        try:
            idx = self._main._side_tabs.indexOf(self._main.site_panel)
            if idx >= 0:
                self._main._side_tabs.setCurrentIndex(idx)
        except Exception:
            pass
        # Persist coordinates immediately; site data fills in when fetcher returns.
        sc = self._main._project["properties"].setdefault("site_config", {})
        sc["latitude"]  = lat
        sc["longitude"] = lng
        if label:
            sc["pin_label"] = label
        self._main._mark_modified()
        self._main._set_mode_label("Property pin set — fetching site data")

    def _on_site_pin_removed(self):
        self._main.site_panel.clear_pin()
        sc = self._main._project["properties"].setdefault("site_config", {})
        for key in ("latitude", "longitude", "pin_label",
                    "rainfall", "soil", "elevation", "hardiness",
                    "data_fetched_at"):
            sc.pop(key, None)
        self._main._mark_modified()
        self._main._set_mode_label("Property pin removed")

    # ── Plant placement / removal handlers ──────────────────────────────────

    def _on_plant_placed(self, plant_id: int, common_name: str,
                          lat: float, lng: float):
        # Single-click placement: each plant gets its own singleton group.
        import src.project as project_io
        group_id = project_io.new_placement_group_id()
        self._main._push_undo({
            "action": "place_plant",
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
            "placement_group_id": group_id,
        })
        self._main._placed_plants.append({
            "plant_id": plant_id, "common_name": common_name,
            "lat": lat, "lng": lng,
            "placement_group_id": group_id,
        })
        self._main._project["features"].append({
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
        self._main.map_widget.set_plant_group_for_latest(plant_id, lat, lng, group_id)
        self._main.plant_panel.on_plant_placed(plant_id, common_name)
        self._main._mark_modified()
        self._main._sync_planning_panel()

    def _on_plant_removed(self, marker_id: str, plant_id: int,
                           lat: float, lng: float):
        # Remove matching entry from placed list (match by plant_id + coords)
        for i, p in enumerate(self._main._placed_plants):
            if (p["plant_id"] == plant_id
                    and abs(p["lat"] - lat) < 1e-7
                    and abs(p["lng"] - lng) < 1e-7):
                self._main._placed_plants.pop(i)
                break

        # Remove matching feature from project
        removed = False
        kept = []
        for f in self._main._project["features"]:
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
        self._main._project["features"] = kept

        self._main.plant_panel.on_plant_removed(plant_id)
        self._main._mark_modified()
        self._main._sync_planning_panel()

    def _on_polyculture_removed(self, polyculture_name: str,
                                  center_lat: float, center_lng: float):
        """Remove all polyculture member plant features from project state.

        Members are identified by the polyculture_center_{lat,lng} anchor they were
        tagged with at placement time — the previous approach of matching
        each plant's own coordinate against the center with a 0.001-degree
        (~111 m) tolerance both missed members farther than 100 m from the
        center and could match plants from adjacent polycultures with identical
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
        for p in self._main._placed_plants:
            if (p.get("polyculture_name") == polyculture_name
                    and _anchors_match(p.get("polyculture_center_lat"),
                                       p.get("polyculture_center_lng"))):
                continue  # drop this polyculture member
            kept_plants.append(p)
        removed_count = len(self._main._placed_plants) - len(kept_plants)
        self._main._placed_plants = kept_plants

        kept_features = []
        for f in self._main._project["features"]:
            props = f.get("properties", {})
            if (props.get("element_type") == "plant"
                    and props.get("polyculture_name") == polyculture_name
                    and _anchors_match(props.get("polyculture_center_lat"),
                                       props.get("polyculture_center_lng"))):
                continue  # drop this polyculture member
            kept_features.append(f)
        self._main._project["features"] = kept_features

        # Update plant panel counts
        for _ in range(removed_count):
            self._main.plant_panel.on_plant_removed(0)
        self._main._mark_modified()
        self._main._sync_planning_panel()

    # ── Terrain bbox handlers ────────────────────────────────────────────────

    def _on_terrain_bbox_cancelled(self):
        self._main._pending_terrain_config = None
        self._main._set_mode_label("Ready")
        self._main.site_panel.set_auto_terrain_status("Cancelled.")
