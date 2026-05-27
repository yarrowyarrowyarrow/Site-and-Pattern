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
