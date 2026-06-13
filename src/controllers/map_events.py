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

from src.climate import get_zone, zone_label
from src.project_store import store_for


def _when_from_config(config: dict):
    """Naive local-solar datetime for a shade request, or None for the
    season-average envelope. Accepts ``(month, day, hour)`` or
    ``(month, day, hour, minute)`` (minute defaults to 0, for the sub-hour time
    slider). Pure / Qt-free so it can be unit-tested directly."""
    from datetime import datetime
    w = (config or {}).get("when")
    if not w:
        return None
    minute = int(w[3]) if len(w) > 3 else 0
    return datetime(2025, int(w[0]), int(w[1]), int(w[2]), minute)


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
        from src.db.structures import get_structure, EXISTING_FEATURE_IDS

        # V1.49: reserved ids mean the user marked an EXISTING on-site tree /
        # building (a shade caster for the generator), not a placeable
        # structure. Write the existing_* feature type the shade model reads.
        if struct_id in EXISTING_FEATURE_IDS:
            self._on_existing_feature_placed(struct_id, name, lat, lng, size_m)
            return

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

    def _on_existing_feature_placed(self, struct_id: str, name: str,
                                    lat: float, lng: float, size_m: float):
        """Persist a user-marked existing tree/building (V1.49) as the
        existing_* feature type the generator's shade model reads. Height comes
        from the mode controller's stash (the JS callback doesn't echo it)."""
        from src.db.structures import EXISTING_TREE_ID
        height_m = getattr(self._main, "_existing_feature_height_m", None)
        etype = ("existing_tree" if struct_id == EXISTING_TREE_ID
                 else "existing_building")
        props = {
            "element_type": etype,
            "height_m": float(height_m) if height_m else (
                6.0 if etype == "existing_tree" else 5.0),
            # size_m is the diameter; the shade model wants a radius.
            "canopy_radius_m": max(0.5, float(size_m) / 2.0),
            "label": name,
            # keep struct identity so right-click removal (which emits the
            # struct path) can find and drop this feature too.
            "struct_id": struct_id,
            "size_m": size_m,
        }
        self._main._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": props,
        })
        self._main._push_undo({
            "action": "place_structure", "struct_id": struct_id,
            "name": name, "lat": lat, "lng": lng, "size_m": size_m,
            "struct_def": {"id": struct_id, "name": name, "size_m": size_m},
        })
        self._main._mark_modified()
        self._main.statusBar().showMessage(f"Marked {name}", 2000)

    def _on_structure_removed(self, marker_id: str, struct_id: str,
                               lat: float, lng: float):
        kept = []
        removed = False
        # Existing tree/building marks ride the structure-removal path too
        # (V1.49) — match them alongside real structures.
        _removable = {"structure", "existing_tree", "existing_building"}
        for f in self._main._project["features"]:
            props = f.get("properties", {})
            coords = f.get("geometry", {}).get("coordinates", [])
            if (not removed
                    and props.get("element_type") in _removable
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
                            fill_opacity: float, dash_array: str, area_m2: float,
                            height_m: float = 0.0):
        import json as _json
        points = _json.loads(points_json)
        # Store as GeoJSON Polygon (lng, lat; closed ring)
        ring = [[pt[1], pt[0]] for pt in points]
        ring.append(ring[0])  # close the ring
        # A height > 0 makes this a shade-casting footprint (a drawn canopy or
        # building perimeter). It's tagged element_type "canopy_footprint" with
        # cast_shade=True so shade.casters_from_project picks it up as a true
        # polygon caster; the footprint geometry stays here in the project file.
        casts_shade = bool(height_m and height_m > 0)
        props = {
            "element_type": "canopy_footprint" if casts_shade else "custom_shape",
            "shape_id": shape_id,
            "label": label,
            "shape_type": shape_type,
            "fill_color": fill_color,
            "stroke_color": stroke_color,
            "fill_opacity": fill_opacity,
            "dash_array": dash_array,
            "area_m2": area_m2,
        }
        if casts_shade:
            props["height_m"] = float(height_m)
            props["cast_shade"] = True
            # Size the footprint from its ring so the keep-out / circle fallback
            # match the drawn shape rather than a hard-coded default.
            from src.osm_features import ring_radius_m
            props["canopy_radius_m"] = max(0.5, ring_radius_m(ring))
            # A drawn tree canopy casts a tapering tree shadow, not a building
            # extrusion (see shade.casters_from_project / cast_tree_shadow).
            if shape_type == "Tree canopy":
                props["caster_kind"] = "tree"
        self._main._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": props,
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
        extra = f", {height_m:.1f} m tall — casts shade" if casts_shade else ""
        # Lawn-conversion zone (N2): report the running converted total.
        from src.lawn_zones import is_zone_label, conversion_summary
        if is_zone_label(shape_type):
            summ = conversion_summary(self._main._project["features"])
            self._main.statusBar().showMessage(
                f"Zone added: {label or shape_type} ({area_str}). "
                f"Converted so far: {summ['converted_m2']:,.0f} m² "
                f"({summ['pct_converted']:.0f}% of lawn+restoration); "
                f"lawn left: {summ['lawn_remaining_m2']:,.0f} m².", 6000
            )
        else:
            self._main.statusBar().showMessage(
                f"Shape placed: {label or shape_type} ({area_str}{extra})", 3000
            )
        if casts_shade:
            self._refresh_shade_if_active()   # new caster updates a live overlay

    def _on_shape_removed(self, shape_id: str):
        feats = self._main._project["features"]
        removed_caster = any(
            f.get("properties", {}).get("shape_id") == shape_id
            and f.get("properties", {}).get("cast_shade")
            for f in feats
        )
        self._main._project["features"] = [
            f for f in feats
            if f.get("properties", {}).get("shape_id") != shape_id
        ]
        self._main._mark_modified()
        if removed_caster:
            self._refresh_shade_if_active()   # shadow must follow its caster

    def _on_shape_height_changed(self, shape_id: str, height_m: float):
        """Update a drawn shape's height in place (map right-click 'edit
        height'). A positive height makes it a shade-casting canopy_footprint;
        the JS side has already re-rendered the polygon."""
        casts = bool(height_m and height_m > 0)
        for f in self._main._project["features"]:
            props = f.get("properties", {})
            if props.get("shape_id") != shape_id:
                continue
            props["element_type"] = "canopy_footprint" if casts else "custom_shape"
            props["height_m"] = float(height_m) if casts else None
            props["cast_shade"] = True if casts else None
            if casts and not props.get("canopy_radius_m"):
                from src.osm_features import ring_radius_m
                ring = (f.get("geometry", {}).get("coordinates") or [None])[0]
                if ring:
                    props["canopy_radius_m"] = max(0.5, ring_radius_m(ring))
            self._main._mark_modified()
            self._main.statusBar().showMessage(
                f"Shade height updated to {height_m:.1f} m.", 3000)
            break
        self._refresh_shade_if_active()

    def _on_shape_geom_changed(self, shape_id: str, points: list):
        """A drawn/imported shape's outline was dragged in edit mode — update the
        project geometry and refresh a live shade overlay so the shadow follows
        the edited footprint. Thin wrapper over project.update_shape_geometry."""
        from src.project import update_shape_geometry
        if update_shape_geometry(self._main._project, shape_id, points):
            self._main._mark_modified()
        self._refresh_shade_if_active()

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
        from PyQt6.QtWidgets import QInputDialog
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
        store_for(self._main).move_plant(
            plant_id, old_lat, old_lng, new_lat, new_lng)
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
            store_for(self._main).move_plant(
                orig.get("plantId"), old_lat, old_lng, new_lat, new_lng,
                group_id=group_id)
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

    def _on_selection_moved(self, originals_json: str, moved_json: str):
        """User dragged a marquee selection of plants as a unit (G1). Unlike
        ``_on_plant_group_moved`` this matches features by ``plant_id`` + old
        coordinates *without* a placement-group constraint, so a selection
        spanning several groups (or ungrouped plants) updates correctly."""
        import json as _json
        try:
            originals = _json.loads(originals_json or "[]")
            moved = _json.loads(moved_json or "[]")
        except Exception:
            return
        if not originals or len(originals) != len(moved):
            return
        moved_by_id = {m.get("markerId"): m for m in moved}
        any_change = False
        for orig in originals:
            new = moved_by_id.get(orig.get("markerId"))
            if not new:
                continue
            old_lat, old_lng = float(orig.get("lat") or 0.0), float(orig.get("lng") or 0.0)
            new_lat, new_lng = float(new.get("lat") or 0.0), float(new.get("lng") or 0.0)
            if abs(new_lat - old_lat) < 1e-9 and abs(new_lng - old_lng) < 1e-9:
                continue
            if store_for(self._main).move_plant(
                    orig.get("plantId"), old_lat, old_lng,
                    new_lat, new_lng):
                any_change = True
        if not any_change:
            return
        self._main._push_undo({
            "action": "move_selection",
            "originals": list(originals),
            "moved": list(moved),
        })
        self._main._mark_modified()
        self._main.statusBar().showMessage(
            f"Moved selection ({len(originals)} plants)", 2000
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
        store_for(self._main).add_plant(
            plant_id, common_name, lat, lng, placement_group_id=group_id)
        # Tell JS the marker's group id so right-click → "Delete group" works.
        self._main.map_widget.set_plant_group_for_latest(plant_id, lat, lng, group_id)
        self._main.plant_panel.on_plant_placed(plant_id, common_name)
        self._main._mark_modified()
        self._main._sync_planning_panel()

    def _on_plant_removed(self, marker_id: str, plant_id: int,
                           lat: float, lng: float):
        store_for(self._main).remove_plant(plant_id, lat, lng)
        self._main.plant_panel.on_plant_removed(plant_id)
        self._main._mark_modified()
        self._main._sync_planning_panel()

    def _on_plants_removed_batch(self, batch_json: str):
        """Remove many plants in one pass — one feature rebuild + one planning
        re-sync for the whole selection, instead of the per-plant round-trip
        (each of which recomputed the habitat score) that made multi-delete lag.
        """
        import json as _json
        try:
            batch = _json.loads(batch_json or "[]")
        except Exception:
            return
        if not batch:
            return
        main = self._main

        removed_ids = [int(d["plantId"]) for d in batch]
        store_for(main).remove_plants_batch(
            (d["plantId"], d["lat"], d["lng"]) for d in batch)

        # One panel rebuild + one re-sync for the whole batch.
        main.plant_panel.on_plants_removed_batch(removed_ids)
        main._mark_modified()
        main._sync_planning_panel()

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
        removed_count = store_for(self._main).remove_polyculture(
            polyculture_name, center_lat, center_lng)

        # Update plant panel counts
        for _ in range(removed_count):
            self._main.plant_panel.on_plant_removed(0)
        self._main._mark_modified()
        self._main._sync_planning_panel()

    # ── Auto-terrain pipeline ────────────────────────────────────────────────
    # Spans both MapBridge slots (bbox_cancelled / bbox_ready) and worker
    # signals (ready / failed / thread_done). All terrain-queue state
    # (_pending_terrain_config, _terrain_queue, _terrain_running,
    # _terrain_render_prefs, _terrain_thread, _terrain_worker) lives on
    # MainWindow; the controller pokes it through self._main.

    def _on_auto_terrain_requested(self, config: dict):
        """Stash config, then ask the JS map for the bbox to compute over."""
        self._main._pending_terrain_config = dict(config)
        area = config.get("area_source", "viewport")
        if area == "viewport":
            self._main.map_widget.request_terrain_viewport()
        elif area == "boundary":
            self._main.map_widget.request_terrain_boundary_bbox()
        elif area == "draw":
            self._main.map_widget.enter_terrain_draw_mode()
            self._main._set_mode_label(
                "Drag a rectangle on the map to set the slope-analysis area"
            )

    def _on_terrain_bbox_cancelled(self):
        self._main._pending_terrain_config = None
        self._main._set_mode_label("Ready")
        self._main.site_panel.set_auto_terrain_status("Cancelled.")

    def _on_terrain_bbox_ready(self, bbox: dict):
        """Enqueue a TerrainWorker job for the chosen bbox and start it
        if no other job is running. Multiple Generate clicks queue up
        rather than getting rejected.
        """
        cfg = getattr(self._main, "_pending_terrain_config", None)
        if not cfg:
            return
        self._main._pending_terrain_config = None

        options = {
            "interval_m":         cfg.get("interval_m", 0.5),
            "resolution_m":       cfg.get("resolution_m", 30.0),
            "want_contours":      cfg.get("want_contours", True),
            "want_slope_overlay": cfg.get("want_slope_overlay", True),
        }
        prefs = {
            "color":       cfg.get("color", "#44cc00"),
            "opacity":     cfg.get("opacity", 0.6),
            "show_labels": cfg.get("show_labels", True),
        }
        if not hasattr(self._main, "_terrain_queue"):
            self._main._terrain_queue = []
        self._main._terrain_queue.append({
            "bbox": bbox, "options": options, "prefs": prefs,
        })
        self._update_terrain_queue_status()
        self._maybe_start_next_terrain_job()

    def _maybe_start_next_terrain_job(self):
        """Pop the next queued job and run it, if nothing else is running."""
        if getattr(self._main, "_terrain_running", False):
            return
        queue = getattr(self._main, "_terrain_queue", None) or []
        if not queue:
            return
        job = queue.pop(0)
        bbox    = job["bbox"]
        options = job["options"]
        self._main._terrain_render_prefs = job["prefs"]

        from PyQt6.QtCore import QThread
        from src.terrain import TerrainWorker, grid_dims
        self._main._terrain_running = True
        self._main._terrain_thread = QThread(self._main)
        self._main._terrain_worker = TerrainWorker(bbox, options)
        self._main._terrain_worker.moveToThread(self._main._terrain_thread)
        self._main._terrain_thread.started.connect(self._main._terrain_worker.run)
        self._main._terrain_worker.ready.connect(self._on_terrain_ready)
        self._main._terrain_worker.failed.connect(self._on_terrain_failed)
        self._main._terrain_worker.finished.connect(self._main._terrain_thread.quit)
        self._main._terrain_worker.finished.connect(
            self._main._terrain_worker.deleteLater
        )
        self._main._terrain_thread.finished.connect(self._on_terrain_thread_done)
        self._main._terrain_thread.start()

        self._main._set_mode_label("Generating slope contours…")
        cols, rows = grid_dims(bbox, options["resolution_m"])
        n_samples = cols * rows
        prefix = self._terrain_queue_prefix()
        if n_samples > 3000:
            # ~0.3 s pacing per batch + request time ≈ 0.5 s/batch end-to-end.
            est_seconds = max(5, int(round(n_samples / 100 * 0.6)))
            self._main.site_panel.set_auto_terrain_status(
                f"{prefix}Fetching elevation data for {cols}×{rows} samples "
                f"— ~{est_seconds} s for an area this size…"
            )
        else:
            self._main.site_panel.set_auto_terrain_status(
                f"{prefix}Fetching elevation data…"
            )

    def _terrain_queue_prefix(self) -> str:
        """Render '[3 queued] ' before status text when other jobs wait."""
        queued = len(getattr(self._main, "_terrain_queue", []) or [])
        return f"[{queued} more queued] " if queued else ""

    def _update_terrain_queue_status(self):
        """Update the status line when queue changes but no job started yet."""
        queue = getattr(self._main, "_terrain_queue", []) or []
        if not getattr(self._main, "_terrain_running", False) and queue:
            self._main.site_panel.set_auto_terrain_status(
                f"Queued {len(queue)} job(s); starting next…"
            )

    def _on_terrain_thread_done(self):
        """Clear stale references after a TerrainWorker run finishes, then
        start the next queued job (if any).

        Connected to QThread.finished. Drops the Python references *before*
        scheduling deleteLater on the thread, so the next Generate click
        can't observe a half-deleted wrapper.
        """
        from PyQt6.QtCore import QTimer
        thread = self._main._terrain_thread
        self._main._terrain_thread = None
        self._main._terrain_worker = None
        self._main._terrain_running = False
        if thread is not None:
            thread.deleteLater()
        # Defer the next start so deleteLater settles cleanly.
        QTimer.singleShot(0, self._maybe_start_next_terrain_job)

    def _on_terrain_ready(self, result: dict):
        """Render the worker's output and persist features in the project."""
        prefs = getattr(self._main, "_terrain_render_prefs", {}) or {}
        contours = result.get("contours") or []
        png_bytes = result.get("slope_png_bytes")
        slope_bbox = result.get("slope_bbox")

        # Strip stale auto features before adding new ones.
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if f.get("properties", {}).get("element_type") not in
                ("auto_contour", "slope_overlay")
        ]
        self._main.map_widget.clear_auto_terrain()

        # Render contour lines.
        if contours:
            self._main.map_widget.draw_auto_contours(
                contours,
                color=prefs.get("color", "#44cc00"),
                show_labels=prefs.get("show_labels", True),
            )
            for c in contours:
                # Each contour may have multiple disjoint segments;
                # stored as a MultiLineString feature for round-tripping.
                lines = []
                for seg in c.get("segments", []):
                    if len(seg) >= 2:
                        # GeoJSON wants [lng, lat]
                        lines.append([[pt[1], pt[0]] for pt in seg])
                if not lines:
                    continue
                self._main._project["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": lines,
                    },
                    "properties": {
                        "element_type": "auto_contour",
                        "elevation_m":  c["elevation_m"],
                        "color":        prefs.get("color", "#44cc00"),
                        "source":       result.get("source", ""),
                    },
                })

        # Render slope ramp overlay.
        if png_bytes and slope_bbox:
            import base64
            data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
            self._main.map_widget.draw_slope_overlay(
                data_url, slope_bbox,
                opacity=prefs.get("opacity", 0.6),
            )
            # Persist a marker feature so projects re-open with overlay
            # information (the PNG itself is regenerated on demand).
            ring = [
                [slope_bbox["west"], slope_bbox["south"]],
                [slope_bbox["east"], slope_bbox["south"]],
                [slope_bbox["east"], slope_bbox["north"]],
                [slope_bbox["west"], slope_bbox["north"]],
                [slope_bbox["west"], slope_bbox["south"]],
            ]
            self._main._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "element_type": "slope_overlay",
                    "bbox":         slope_bbox,
                    "stats":        result.get("stats", {}),
                    "interval_m":   result.get("interval_m"),
                    "resolution_m": result.get("resolution_m"),
                    "source":       result.get("source", ""),
                },
            })

        self._main._mark_modified()
        self._main._set_mode_label("Ready")

        stats = result.get("stats", {})
        bits = [f"Source: {result.get('source', '')}"]
        if "max_slope_pct" in stats:
            bits.append(
                f"Max slope: {stats['max_slope_pct']:.1f}%, "
                f"mean: {stats.get('mean_slope_pct', 0):.1f}%"
            )
        if "dominant_aspect" in stats:
            share_pct = int(round(stats.get("dominant_aspect_share", 0) * 100))
            bits.append(
                f"Aspect: {stats['dominant_aspect']} ({share_pct}% of slope ≥2%)"
            )
        bits.append(f"{len(contours)} contour level(s)")
        for w in (result.get("warnings") or []):
            bits.append("⚠ " + w)
        self._main.site_panel.set_auto_terrain_status(" — ".join(bits))

    def _on_terrain_failed(self, message: str):
        from PyQt6.QtWidgets import QMessageBox
        self._main._set_mode_label("Ready")
        self._main.site_panel.set_auto_terrain_status(f"Failed: {message}")
        # Avoid stacking modal dialogs when more jobs are queued — show
        # one only when nothing else is pending. Queued failures still
        # surface in the status line.
        queued = len(getattr(self._main, "_terrain_queue", []) or [])
        if queued == 0:
            QMessageBox.warning(self._main, "Terrain Generation", message)

    def _on_auto_terrain_cleared(self):
        self._main.map_widget.clear_auto_terrain()
        self._main._project["features"] = [
            f for f in self._main._project["features"]
            if f.get("properties", {}).get("element_type") not in
                ("auto_contour", "slope_overlay")
        ]
        self._main._mark_modified()
        self._main.site_panel.set_auto_terrain_status("")

    # ── Shade overlay (V1.51) ────────────────────────────────────────────────

    def _project_boundary_latlng(self):
        """First drawn boundary as [(lat, lng), …], or None — for shade/zoning."""
        import src.project as project_io
        try:
            data = project_io.project_to_map_data(self._main._project)
        except Exception:  # noqa: BLE001
            return None
        for b in data.get("boundaries", []):
            pts = b.get("points") or []
            if len(pts) >= 3:
                return [(float(p[0]), float(p[1])) for p in pts]
        return None

    def _run_worker(self, worker, on_ready, attr_prefix: str):
        """Run a QObject worker (with ``run``/``ready``/``finished``) on its own
        QThread and auto-tear-down. Keeps a ref on the main window under
        ``_{attr_prefix}_thread``/``_worker`` so it isn't GC'd mid-flight.
        Shared by the shade overlay + zone-classify flows."""
        from PyQt6.QtCore import QThread
        thread = QThread(self._main)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.ready.connect(on_ready)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        setattr(self._main, f"_{attr_prefix}_thread", thread)
        setattr(self._main, f"_{attr_prefix}_worker", worker)
        thread.start()

    def _on_shade_requested(self, config: dict):
        """Compute the shade overlay off-thread and draw it. The elevation fetch
        can be slow/network-bound, so it never blocks the UI.

        Prefers the true-shape vector path (ShadowPolygonWorker) when shapely is
        available — crisp polygon shadows that don't get dropped by the coarse
        elevation grid. Falls back to the raster ShadeWorker without shapely."""
        from src.shade import ShadeWorker, _HAVE_SHAPELY

        sc = dict(self._main._project.get("properties", {})
                  .get("site_config", {}) or {})
        boundary = self._project_boundary_latlng()
        if boundary is None and sc.get("latitude") is None:
            self._main.statusBar().showMessage(
                "Drop a property pin or draw a boundary first.", 4000)
            return

        when = _when_from_config(config)    # (month, day, hour[, minute]) local

        # Remember the request so an outline/height edit can recompute the same
        # view in place (see _refresh_shade_if_active).
        self._main._last_shade_config = dict(config or {})
        self._main._shade_opacity = (
            self._main.site_panel._shade_opacity.value() / 100.0)
        self._main.statusBar().showMessage("Computing shade…")
        if _HAVE_SHAPELY:
            from src.shade import ShadowPolygonWorker
            self._run_worker(
                ShadowPolygonWorker(self._main._project, boundary, sc, when),
                self._on_shadow_polygons_ready, "shade")
        else:
            self._run_worker(ShadeWorker(self._main._project, boundary, sc, when),
                             self._on_shade_ready, "shade")

    def _on_shadow_polygons_ready(self, payload):
        """Draw the true-shape vector shadows. Clears the raster overlay so the
        two never stack, and degrades to the message below when nothing casts."""
        self._main.map_widget.clear_shade_overlay()
        if not payload or not payload.get("polygons"):
            # Also clear any prior vector shadows so scrubbing past sunset fades
            # them out instead of freezing the last frame on screen.
            self._main.map_widget.clear_shadow_polygons()
            self._main._shade_overlay_active = False
            self._main.statusBar().showMessage(
                "No shade to show — mark or import some trees/buildings, or add "
                "trees to the design first.", 5000)
            return
        self._main.map_widget.draw_shadow_polygons(
            payload["polygons"], payload.get("bbox"),
            getattr(self._main, "_shade_opacity", 0.5))
        self._main._shade_overlay_active = True
        self._main.statusBar().showMessage("Shade overlay updated.", 3000)

    def _on_shade_ready(self, payload):
        self._main.map_widget.clear_shadow_polygons()
        if not payload:
            self._main.map_widget.clear_shade_overlay()   # fade out past sunset
            self._main._shade_overlay_active = False
            self._main.statusBar().showMessage(
                "No shade to show — mark or import some trees/buildings, or add "
                "trees to the design first.", 5000)
            return
        self._main.map_widget.draw_shade_overlay(
            payload["data_url"], payload["bbox"],
            getattr(self._main, "_shade_opacity", 0.5))
        self._main._shade_overlay_active = True
        self._main.statusBar().showMessage("Shade overlay updated.", 3000)

    def _on_shade_cleared(self):
        """Clear both shade overlays (raster + vector)."""
        self._main._shade_overlay_active = False
        self._main.map_widget.clear_shade_overlay()
        self._main.map_widget.clear_shadow_polygons()

    def _refresh_shade_if_active(self):
        """Recompute the shade overlay in place after a footprint edit, but only
        when one is currently shown — so editing an outline never pops an overlay
        the user didn't ask for. Reuses the last shade request."""
        if not getattr(self._main, "_shade_overlay_active", False):
            return
        cfg = getattr(self._main, "_last_shade_config", None)
        if cfg is not None:
            self._on_shade_requested(cfg)

    def _on_shade_opacity(self, opacity: float):
        """Drive opacity on whichever shade overlay is showing."""
        self._main._shade_opacity = opacity
        self._main.map_widget.set_shade_overlay_opacity(opacity)
        self._main.map_widget.set_shadow_polygon_opacity(opacity)

    def _on_shade_zones_requested(self):
        """Classify planting cells (full sun / partial / full shade) off the UI
        thread and cache the derived tags (src/db/shade_zones.py)."""
        from src.shade import ShadeZoneWorker

        sc = dict(self._main._project.get("properties", {})
                  .get("site_config", {}) or {})
        boundary = self._project_boundary_latlng()
        if boundary is None and sc.get("latitude") is None:
            self._main.site_panel.set_shade_zone_status(
                "Drop a property pin or draw a boundary first.")
            return

        self._main.site_panel.set_shade_zone_status("Classifying planting zones…")
        self._run_worker(ShadeZoneWorker(self._main._project, boundary, sc),
                         self._on_shade_zones_ready, "shade_zone")

    def _on_shade_zones_ready(self, rows):
        if not rows:
            self._main.site_panel.set_shade_zone_status(
                "Couldn't classify — no terrain grid for this site yet.")
            return
        from src.db import shade_zones
        pk = shade_zones.project_key_for(getattr(self._main, "_project_path", None))
        shade_zones.clear_zone_tags(pk)
        shade_zones.store_zone_tags(pk, rows)
        # Now the tags exist, flag any placed plant whose sun requirement
        # clashes with its spot (full-sun plant in deep shade, etc.).
        try:
            from src.placement_score import check_shade_matches
            mismatches = check_shade_matches(
                getattr(self._main, "_placed_plants", None) or [], pk)
        except Exception:  # noqa: BLE001 — feedback is best-effort
            mismatches = []
        counts = shade_zones.tag_counts(pk)
        self._main.site_panel.set_shade_zone_status(
            shade_zones.format_classification_status(len(rows), counts, mismatches))
        # Mirror the mix into the Analysis tab's read-only breakdown.
        try:
            self._main.analysis_panel.set_shade_breakdown(counts)
        except Exception:  # noqa: BLE001
            pass
        # Draw the classified zones on the map as a coloured grid so the user can
        # see where the sun/partial/shade planting spots are.
        try:
            cells = [{"lat": r["centroid_lat"], "lng": r["centroid_lng"],
                      "tag": r["shade_tag"]} for r in rows
                     if r.get("centroid_lat") is not None]
            d_lat = self._grid_spacing([r["centroid_lat"] for r in rows]) or 0.00004
            d_lng = self._grid_spacing([r["centroid_lng"] for r in rows]) or 0.00006
            if cells:
                self._main.map_widget.draw_shade_zones(cells, d_lat, d_lng)
                self._main.site_panel.mark_zones_shown()
        except Exception:  # noqa: BLE001 — visualisation is best-effort
            pass
        self._main.statusBar().showMessage("Planting zones classified.", 3000)

    @staticmethod
    def _grid_spacing(values) -> float:
        """Smallest positive gap between distinct sorted values — the grid cell
        size in degrees, used to size the drawn shade-zone rectangles."""
        u = sorted({round(float(v), 9) for v in values if v is not None})
        diffs = [b - a for a, b in zip(u, u[1:]) if b - a > 1e-9]
        return min(diffs) if diffs else 0.0

    # ── Existing features from OpenStreetMap (V1.51) ─────────────────────────

    def _on_osm_import_requested(self):
        """Fetch buildings/trees from OSM for the boundary/pin area off-thread,
        then add them as existing_* features (deduped). Degrades gracefully."""
        from src.osm_features import OSMWorker, bbox_from_boundary_or_pin

        sc = dict(self._main._project.get("properties", {})
                  .get("site_config", {}) or {})
        boundary = self._project_boundary_latlng()
        bbox = bbox_from_boundary_or_pin(boundary, sc)
        if bbox is None:
            self._main.site_panel.set_osm_status(
                "Drop a pin or draw a boundary first.")
            return

        # Prefer the offline building pack when this area has been downloaded
        # (instant, no network) — same data, same canopy_footprint pipeline.
        from src import building_flow
        if building_flow.import_buildings_offline(self._main, bbox):
            return

        self._main.site_panel.set_osm_status("Querying OpenStreetMap…")
        self._run_worker(OSMWorker(bbox), self._on_osm_ready, "osm")

    def _on_footprint_import_requested(self, tiff_path: str):
        """Vectorize shade-casting footprints from an nDSM GeoTIFF off-thread."""
        from src.footprint_ndsm import FootprintExtractWorker
        self._main.site_panel.set_osm_status("Reading GeoTIFF…")
        self._run_worker(FootprintExtractWorker(tiff_path),
                         self._on_footprint_import_ready, "footprint")

    def _on_footprint_import_ready(self, payload):
        if payload.get("error"):
            self._main.site_panel.set_osm_status(
                f"Footprint import failed: {payload['error']}")
            return
        from src.footprint_extract import add_extracted_footprints
        from src.project import feature_to_shape
        new_feats = add_extracted_footprints(payload.get("rings") or [],
                                             self._main._project)
        for f in new_feats:                     # render only the new footprints
            self._main.map_widget.load_shape(feature_to_shape(f))
        if new_feats:
            self._main._mark_modified()
        self._main.site_panel.set_osm_status(
            f"Imported {len(new_feats)} footprint(s) from the GeoTIFF."
            if new_feats else "No raised footprints found in that GeoTIFF.")

    def _on_osm_ready(self, res):
        if not res:
            self._main.site_panel.set_osm_status(
                "OpenStreetMap unavailable or nothing found nearby.")
            return
        from src.osm_features import add_features_to_project
        feats = list(res.get("buildings", [])) + list(res.get("trees", []))
        added = add_features_to_project(feats, self._main._project)
        if added:
            self._main._mark_modified()
            # Re-render the newly imported features through the structure path.
            self._reload_existing_features()
        n_b = len(res.get("buildings", []))
        n_t = len(res.get("trees", []))
        self._main.site_panel.set_osm_status(
            f"Found {n_b} building(s), {n_t} tree(s); added {added} new.")

    def _reload_existing_features(self):
        """Draw OSM-imported existing features that aren't yet on the map: trees
        (Point structures) and buildings (V1.58 ``canopy_footprint`` polygons).
        Both render idempotently — ``load_structure`` / ``load_shape`` reuse the
        id and re-draw in place, so calling this after each import is safe."""
        import src.project as project_io
        try:
            data = project_io.project_to_map_data(self._main._project)
        except Exception:  # noqa: BLE001
            return
        for s in data.get("structures", []):
            sd = s.get("struct_def", {})
            if sd.get("id") in ("existing_tree", "existing_building"):
                self._main.map_widget.load_structure(sd, s["lat"], s["lng"])
        # Buildings now arrive as true-outline canopy_footprint polygons — render
        # them through the shape path so the user sees the real footprint.
        for f in self._main._project.get("features", []):
            props = f.get("properties", {}) or {}
            if (props.get("source") == "osm"
                    and props.get("element_type") in ("canopy_footprint",
                                                      "custom_shape")):
                sh = project_io.feature_to_shape(f)
                if sh:
                    self._main.map_widget.load_shape(sh)

    # ── Edmonton offline dataset download ────────────────────────────────────
    # State on MainWindow: _dl_thread, _dl_worker.

    def _on_download_edmonton_requested(self):
        from PyQt6.QtCore import QThread
        from src.terrain_downloader import EdmontonDownloadWorker
        self._main._dl_thread = QThread(self._main)
        self._main._dl_worker = EdmontonDownloadWorker()
        self._main._dl_worker.moveToThread(self._main._dl_thread)
        self._main._dl_thread.started.connect(self._main._dl_worker.run)
        self._main._dl_worker.progress.connect(self._on_edmonton_dl_progress)
        self._main._dl_worker.finished.connect(self._on_edmonton_dl_finished)
        self._main._dl_worker.error.connect(self._on_edmonton_dl_error)
        self._main._dl_worker.finished.connect(self._main._dl_thread.quit)
        self._main._dl_worker.error.connect(self._main._dl_thread.quit)
        self._main._dl_thread.finished.connect(self._on_dl_thread_done)
        # Wire the Cancel button to the worker's cancel() slot
        self._main.site_panel._terrain_cancel_btn.clicked.connect(
            self._main._dl_worker.cancel
        )
        self._main._dl_thread.start()

    def _on_edmonton_dl_progress(self, features_stored: int, page_num: int,
                                   text: str):
        self._main.site_panel.set_download_progress(
            features_stored, page_num, text,
        )

    def _on_edmonton_dl_finished(self, total: int):
        self._main.site_panel.set_terrain_status()
        self._main.statusBar().showMessage(
            f"Edmonton terrain download complete — {total:,} features stored offline.",
            8000,
        )

    def _on_edmonton_dl_error(self, message: str):
        self._main.site_panel.set_terrain_status()
        self._main.statusBar().showMessage(
            f"Edmonton download failed: {message}", 10000,
        )

    def _on_dl_thread_done(self):
        try:
            self._main.site_panel._terrain_cancel_btn.clicked.disconnect(
                self._main._dl_worker.cancel
            )
        except Exception:
            pass
        if (hasattr(self._main, "_dl_worker")
                and self._main._dl_worker is not None):
            self._main._dl_worker.deleteLater()
            self._main._dl_worker = None
        if (hasattr(self._main, "_dl_thread")
                and self._main._dl_thread is not None):
            self._main._dl_thread.deleteLater()
            self._main._dl_thread = None

    def _on_download_buildings_requested(self):
        # Orchestration lives in src/building_flow.py (keeps this controller
        # under its line ceiling); state lands on MainWindow there.
        from src import building_flow
        building_flow.start_building_download(self._main)

    # ── Sun / sector / contour / wind analysis-overlay request slots ────────

    def _on_sun_path_requested(self, config: dict):
        """A1: Enter anchor-placement mode; render after user clicks the map."""
        self._main._pending_sun_config = config
        self._main._pending_sun_anchor = None
        self._main.map_widget.enter_sun_anchor_mode()
        self._main._set_mode_label(
            "Click map to place sun path anchor — right-click to cancel"
        )

    def _on_sector_requested(self, config: dict):
        """A2: Enter anchor-placement mode; draw after user clicks the map."""
        self._main._pending_sector_config = config
        self._main.map_widget.enter_sector_anchor_mode()
        self._main._set_mode_label(
            "Click map to place sector anchor — right-click to cancel"
        )

    def _on_contour_requested(self, config: dict):
        """A3: Enter contour drawing mode."""
        self._main._current_mode = 'contour'
        self._main.map_widget.set_contour_mode(config)
        self._main.toolbar.reset_draw_buttons()
        elev = config.get("elevation_m", 0)
        self._main._set_mode_label(
            f"Drawing contour at {elev:.1f}m — click points, double-click to finish"
        )

    def _on_wind_requested(self, config: dict):
        """A4: Draw wind overlay with shelter zones."""
        self._main.map_widget.draw_wind_overlay(config)
        self._main._set_mode_label(
            f"Wind from {config.get('direction_from', '?')}° "
            f"({config.get('speed_label', '')})"
        )

    def _on_fetch_wind_requested(self):
        """Fetch real seasonal wind + current reading for the site (V1.67).
        Orchestration lives in src/wind_flow.py to keep this controller thin."""
        from src import wind_flow
        wind_flow.fetch_wind_for_site(self._main)

    def _on_download_soil_requested(self):
        """Download the offline soil pack (V1.67). Orchestration in soil_flow."""
        from src import soil_flow
        soil_flow.start_soil_download(self._main)

    # ── Project notes ────────────────────────────────────────────────────────

    def _on_notes_changed(self, text: str):
        self._main._project["properties"]["notes"] = text
        self._main._mark_modified()

    # ── Manual pin drop + address resolve + reverse geocode ─────────────────

    def _on_site_pin_clear_clicked(self):
        self._main.map_widget.clear_site_pin()
        self._on_site_pin_removed()

    def _on_address_resolved(self, lat: float, lng: float, label: str):
        """SitePanel resolved an address — drop the pin and re-centre the map.

        The bridge will fire `site_pin_placed` back which runs the
        existing site-data fetch flow; we just have to place the pin
        and pan/zoom.
        """
        self._main.map_widget.place_site_pin(lat, lng, label or "")
        # Centre on the new pin at a reasonable property-scale zoom.
        self._main.map_widget.set_view(lat, lng, 17)

    def _on_site_pin_click(self, lat: float, lng: float):
        if not getattr(self._main, "_site_pin_mode", False):
            return
        self._main._site_pin_mode = False
        self._main.map_widget.set_site_pin_drop_mode(False)
        try:
            self._main.map_widget.bridge.map_clicked.disconnect(
                self._main._on_site_pin_click
            )
        except Exception:
            pass
        # Drop the pin immediately with just coordinates so the user gets
        # instant feedback, then resolve the actual address in the
        # background and refresh the pin label once we have it.
        self._main.map_widget.place_site_pin(lat, lng, "")
        self._main._start_pin_reverse_geocode(lat, lng)

    def _on_pin_reverse_geocode_done(self, lat: float, lng: float,
                                       label: str):
        self._main._revgeo_worker = None
        self._main._revgeo_thread = None
        if not label:
            return
        # Re-place the pin with the resolved label so the marker tooltip
        # and the Site panel both show the actual address.
        self._main.map_widget.place_site_pin(lat, lng, label)

    def _on_site_data_updated(self, result: dict):
        """SitePanel finished fetching; persist results into project state."""
        from src.project import _utc_now_iso
        sc = self._main._project["properties"].setdefault("site_config", {})
        for key in ("rainfall", "soil", "elevation", "hardiness"):
            if result.get(key) is not None:
                sc[key] = result[key]
        # Make soil actionable: pH/texture → flat site_config + plant matching.
        from src import soil_flow
        soil_flow.apply_soil_site_fields(self._main, result.get("soil"))
        sc["data_fetched_at"] = _utc_now_iso()

        # Mirror the auto-filled hardiness zone into the existing
        # top-level project field so the rest of the app picks it up.
        hard = result.get("hardiness") or {}
        zone = hard.get("zone")
        if zone is not None:
            self._main._set_zone_display(zone)

        self._main._mark_modified()
        self._main._set_mode_label("Site data ready")

    # ── Season view + growth timeline ────────────────────────────────────────

    def _on_season_changed(self, season: str):
        """Apply seasonal view to the map — adjusts plant visibility by type."""
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
        for p in self._main._placed_plants:
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

        self._main.map_widget.set_season_view(season, pid_vis)
        self._main._set_mode_label(f"Season: {season}")

    def _on_timeline_year_changed(self, year: int):
        """Compute per-plant scale factors for the timeline year and send to JS."""
        import math

        from src.db.plants import get_plant
        from src.succession import (
            successional_role, presence_factor, restoration_stage,
        )

        _DEFAULT_YTM = {"tree": 15, "shrub": 5, "herb": 2, "groundcover": 1,
                        "vine": 2, "root": 2}

        # Build a mapping from markerId patterns to placed plants
        # MarkerIds follow pattern: {plantId}_{timestamp}_{random}
        # We need to iterate plantMarkers in JS, so we build scale data keyed by markerIds
        # Since we don't have JS markerIds in Python, we build per-plant-id scale factors
        # and let JS match by plantId
        plant_cache = {}  # plant_id -> (ytm, curve, ptype, role)
        summary_trees = 0
        summary_mature = 0
        summary_fading = 0
        summary_emerging = 0
        summary_total = len(self._main._placed_plants)

        for p in self._main._placed_plants:
            pid = p["plant_id"]
            if pid not in plant_cache:
                plant = get_plant(pid)
                if plant:
                    ytm = plant.get("years_to_maturity") or _DEFAULT_YTM.get(
                        plant.get("plant_type", "herb"), 2)
                    curve = plant.get("growth_curve") or "steady"
                    ptype = plant.get("plant_type", "herb")
                    role = successional_role(plant)
                else:
                    ytm = 2
                    curve = "steady"
                    ptype = "herb"
                    role = "mid"
                plant_cache[pid] = (ytm, curve, ptype, role)

            ytm, curve, ptype, role = plant_cache[pid]
            pres = presence_factor(role, year, ytm)
            if role == "pioneer" and pres < 0.9:
                summary_fading += 1
            elif role == "climax" and pres < 0.9:
                summary_emerging += 1

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
                f"Year {year} — {restoration_stage(year)}: "
                f"{summary_mature}/{summary_total} plants at maturity "
                f"({pct_mature}%)."
            )
            if summary_fading:
                summary += (
                    f"\n{summary_fading} pioneer "
                    f"species fading as the canopy fills in."
                )
            if summary_emerging:
                summary += (
                    f"\n{summary_emerging} climax species still coming up."
                )
            if summary_trees > 0:
                # Find avg tree scale
                tree_scales = []
                for p in self._main._placed_plants:
                    pid = p["plant_id"]
                    ytm, curve, ptype, role = plant_cache[pid]
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

        self._main.planning_panel.update_timeline_summary(summary)

        # Send scale data to JS — we use a per-plantId approach
        # JS will iterate plantMarkers and look up scaleFactor by plantId.
        # pid_presence carries the succession fade (pioneers out, climax in).
        from src.scene3d import growth_scale_factor
        pid_factors = {}
        pid_presence = {}
        for pid, (ytm, curve, ptype, role) in plant_cache.items():
            # Shared with the (future) 3D view via src.scene3d so the two never
            # drift on the growth curve.
            pid_factors[pid] = growth_scale_factor(year, ytm, curve)
            pid_presence[pid] = presence_factor(role, year, ytm)

        self._main.map_widget.set_timeline_year_by_plant_id(
            year, pid_factors, pid_presence)

    # ── Polyculture click placement ──────────────────────────────────────────

    def _on_polyculture_click(self, lat: float, lng: float):
        """Drop a polyculture by issuing one placePlantMarker per member.

        Mirrors the grid/row/burst loop in _on_pattern_placed: each member is
        rendered through the fast canvas-renderer path with a shared groupId,
        so the placement avoids the per-poly SVG renderer + temp L.layerGroup
        attach that caused O(N^2) browser paint cost. Mode stays armed after
        each placement (Esc / mode-switch cancels), matching row/burst/grid
        UX so a single "Place on Map" press lets the user drop many
        polycultures back to back.
        """
        if (self._main._current_mode != 'polyculture'
                or not hasattr(self._main, '_pending_polyculture')):
            return
        import math
        import src.project as project_io
        # _member_color lives at module level in src.app — lazy import to
        # break the controller→MainWindow import cycle.
        from src.app import _member_color

        polyculture = self._main._pending_polyculture
        members = polyculture.get("members", [])
        if not members:
            return

        poly_name = polyculture.get("name", "")
        group_id = project_io.new_placement_group_id()
        community_id = project_io.community_id_for(lat, lng)
        cos_lat = math.cos(lat * math.pi / 180) or 1e-9

        batch_placements: list[tuple[int, str]] = []
        for m in members:
            pid = m["plant_id"]
            name = m["common_name"]
            spacing_m, plant_type, _ = self._main._plant_info(pid)
            color = _member_color(m)

            mlat = lat + (m.get("offset_y", 0)) / 111320
            mlng = lng + (m.get("offset_x", 0)) / (111320 * cos_lat)

            self._main.map_widget.place_plant_marker(
                pid, name, mlat, mlng,
                spacing_m=spacing_m, plant_type=plant_type,
                color=color, group_id=group_id, community_id=community_id,
            )
            store_for(self._main).add_plant(
                pid, name, mlat, mlng,
                placement_group_id=group_id,
                polyculture_name=poly_name,
                polyculture_center_lat=lat, polyculture_center_lng=lng)
            batch_placements.append((pid, name))

        # One placed-list rebuild per polyculture click instead of N — see
        # PlantPanel.on_plants_placed_batch for the rationale.
        self._main.plant_panel.on_plants_placed_batch(batch_placements)
        self._main._mark_modified()
        self._main._sync_planning_panel()
        self._main._set_mode_label(
            f"Placed plant community '{poly_name}'. Click again for another, "
            f"or press Esc to finish."
        )
        self._main.statusBar().showMessage(
            f"Placed plant community '{poly_name}' with {len(members)} members", 2500
        )

    # ── Pattern placement (Burst / Row / Grid / Circle, including mixes
    #    and community-as-pattern variants) ───────────────────────────────────

    def _on_pattern_placed(self, plant_id: int, common_name: str,
                            spacing_m: float, plant_type: str,
                            custom_color: str, positions_json: str,
                            pattern_kind: str):
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
        import src.project as project_io
        try:
            positions = _json.loads(positions_json)
        except Exception:
            return
        if not positions:
            return

        # ── Community-mix-as-pattern branch ────────────────────────────
        # When the Communities tab armed a Community Mix (≥2 communities
        # at ratios), each anchor becomes one full community picked by
        # ratio. assign_species takes generic {id, weight} items so the
        # communities pose as "species" here at zero algorithmic cost.
        community_mix = getattr(self._main, "_pending_community_pattern_mix", None)
        if community_mix:
            from src.polyculture import assign_species
            mix_items = [
                {
                    "id": int(c["id"]),
                    "common_name": c.get("name") or "",
                    "spacing_m": 1.0,
                    "plant_type": "community",
                    "color": "",
                    "weight": int(c.get("weight") or 1),
                }
                for c in community_mix
            ]
            try:
                assignments = assign_species(positions, mix_items, "even_split")
            except Exception:
                assignments = [mix_items[0]] * len(positions)
            poly_by_id = {int(c["id"]): c["polyculture"] for c in community_mix}
            # One unit per anchor, each with its own placement_group_id —
            # deleting one community doesn't take out the rest of the row.
            n_units = 0
            for (lat, lng), assignment in zip(positions, assignments):
                community = poly_by_id.get(int(assignment["id"]))
                if not community:
                    continue
                self._main._area_fill._place_community_units(
                    [(lat, lng, community)],
                    project_io.new_placement_group_id(),
                    pattern_kind=pattern_kind,
                )
                n_units += 1
            self._main._mark_modified()
            self._main._sync_planning_panel()
            self._main._set_mode_label(
                f"Placed {n_units} communities from the mix "
                f"({pattern_kind}). Click again for another, or press "
                f"Esc to finish."
            )
            self._main.statusBar().showMessage(
                f"Placed {n_units} communities from the mix "
                f"({pattern_kind})", 3000
            )
            return

        # ── Community-as-pattern branch ────────────────────────────────
        # If a Community was stashed at Place-click time, every anchor
        # position expands into one full community (all its members,
        # offset around the anchor). This sits above the plant-mix
        # branch because the two are mutually exclusive — selecting a
        # community for pattern placement clears any plant mix.
        community = getattr(self._main, "_pending_community_pattern", None)
        if community:
            members = community.get("members") or []
            if not members:
                return
            # All anchors share ONE placement_group_id so "Delete group"
            # removes the whole pattern; each anchor's members carry the
            # per-instance polyculture_center anchor for one-at-a-time
            # community deletion.
            poly_name = community.get("name") or ""
            self._main._area_fill._place_community_units(
                [(lat, lng, community) for (lat, lng) in positions],
                project_io.new_placement_group_id(),
                pattern_kind=pattern_kind,
            )
            self._main._mark_modified()
            self._main._sync_planning_panel()
            self._main._set_mode_label(
                f"Placed {len(positions)} × '{poly_name}' ({pattern_kind}). "
                "Click again for another, or press Esc to finish."
            )
            self._main.statusBar().showMessage(
                f"Placed {len(positions)} communities of '{poly_name}' "
                f"({len(members)} members each)",
                3000,
            )
            return

        # Peek (don't consume) the polyculture recipe stashed at
        # Place-click time. Keeping it alive lets the user drop multiple
        # back-to-back patterns without re-clicking Place Mix; it's
        # only cleared when plant mode is exited (Esc / cancel) or the
        # user clicks Place Mix again with a different mix.
        assignments: list[dict] | None = None
        poly = None
        try:
            poly = self._main.plant_panel.peek_pending_polyculture()
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
            self._main.map_widget.place_plant_marker(
                pid, name, lat, lng,
                spacing_m=sp_space, plant_type=sp_type,
                color=sp_color or None, group_id=group_id,
            )
            # Mirror in project state.
            store_for(self._main).add_plant(
                pid, name, lat, lng, placement_group_id=group_id,
                pattern_kind=pattern_kind)
            self._main.plant_panel.on_plant_placed(pid, name)
        self._main._mark_modified()
        self._main._sync_planning_panel()
        if assignments is not None:
            n_species = len({s["id"] for s in poly["species"]})
            self._main.statusBar().showMessage(
                f"Placed {len(positions)} plants — "
                f"{n_species}-species plant community ({pattern_kind})", 3000
            )
            self._main._set_mode_label(
                f"Placed plant community ({pattern_kind}). Click again for another, "
                f"or press Esc to finish."
            )
        else:
            self._main.statusBar().showMessage(
                f"Placed {len(positions)} {common_name} ({pattern_kind})", 2500
            )
