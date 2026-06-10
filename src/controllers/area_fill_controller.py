"""
src/controllers/area_fill_controller.py — place a polygon fill (N3′).

Turns the pure ``area_fill.plan_fill`` output into placed plants using the same
dual-store bookkeeping (``_placed_plants`` + ``_project['features']`` + a shared
placement group) as the design generator, so rendering, undo-as-a-unit, the
habitat score and the cost readout all work on a filled area exactly as they do
for a generated or hand-placed design.
"""

from __future__ import annotations

from src import area_fill


class AreaFillController:
    def __init__(self, main):
        self._main = main

    def fill(self, ring, member_specs, spacing_m: float,
             poly_name: str = "", jitter: float = 0.0, rng=None) -> int:
        """Fill a polygon ``ring`` (``[lng, lat]`` pairs) with plants.

        ``member_specs`` is ``[(plant_id, weight), ...]`` — one entry for a single
        species, or a community's members (equal weights by default). Returns the
        number of plants placed. All placements share one group id so the fill
        deletes as a unit."""
        records = area_fill.plan_fill(ring, member_specs, spacing_m, jitter, rng)
        if not records:
            return 0

        main = self._main
        import src.project as project_io
        group_id = project_io.new_placement_group_id()

        # Resolve names once per distinct plant_id.
        name_cache: dict = {}

        def _name(pid):
            if pid not in name_cache:
                try:
                    from src.db.plants import get_plant
                    rec = get_plant(pid) or {}
                except Exception:
                    rec = {}
                name_cache[pid] = rec.get("common_name", "") or f"Plant #{pid}"
            return name_cache[pid]

        batch: list = []
        for pid, lat, lng in records:
            name = _name(pid)
            try:
                spacing, plant_type, _ = main._plant_info(pid)
            except Exception:
                spacing, plant_type = spacing_m, None
            community_id = project_io.community_id_for(lat, lng)
            main.map_widget.place_plant_marker(
                pid, name, lat, lng, spacing_m=spacing, plant_type=plant_type,
                color=None, group_id=group_id, community_id=community_id)
            main._placed_plants.append({
                "plant_id": pid, "common_name": name, "lat": lat, "lng": lng,
                "polyculture_name": poly_name,
                "placement_group_id": group_id,
            })
            main._project["features"].append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {
                    "element_type": "plant",
                    "plant_id": pid,
                    "common_name": name,
                    "polyculture_name": poly_name,
                    "placement_group_id": group_id,
                    "pattern_kind": "area_fill",
                },
            })
            batch.append((pid, name))

        try:
            main.plant_panel.on_plants_placed_batch(batch)
        except Exception:
            pass
        main._mark_modified()
        main._sync_planning_panel()
        main.statusBar().showMessage(
            f"Filled area — placed {len(batch)} plants"
            + (f" from “{poly_name}”" if poly_name else "")
            + ". Fine-tune by dragging or deleting.", 5000)
        return len(batch)

    def fill_communities(self, ring, polyculture: dict, spacing_m: float,
                         rng=None) -> int:
        """Fill a polygon with whole community UNITS — each anchor expands every
        member at its designed ``offset_x``/``offset_y``, exactly like a single
        community placement — rather than scattering individual member plants.

        Anchors sit on a hex grid stepped by the community's natural footprint
        diameter plus ``spacing_m`` (the Communities tab's cell spacing, here the
        gap *between* units). Returns the number of community units placed. All
        units share one placement group so the fill deletes as a unit."""
        import math
        from src.db.polycultures import community_natural_radius

        members = (polyculture or {}).get("members") or []
        if not members:
            return 0
        radius = community_natural_radius(polyculture)
        step = 2.0 * radius + max(0.0, float(spacing_m or 0.0))
        anchors = area_fill.fill_points(ring, step, 0.0, rng)
        if not anchors:
            # Area too small for the grid but maybe one unit still fits — drop a
            # single community at the centroid when it lies inside the polygon.
            from src.osm_features import ring_centroid
            from src.geometry import point_in_ring
            c = ring_centroid(ring)
            if c is not None and point_in_ring(c[0], c[1], ring):
                anchors = [(c[0], c[1])]
            else:
                return 0

        main = self._main
        import src.project as project_io
        from src.member_colors import member_color
        poly_name = polyculture.get("name", "")
        group_id = project_io.new_placement_group_id()

        batch: list = []
        for alat, alng in anchors:
            community_id = project_io.community_id_for(alat, alng)
            cos_lat = math.cos(alat * math.pi / 180) or 1e-9
            for m in members:
                pid = m["plant_id"]
                name = m.get("common_name", "") or f"Plant #{pid}"
                try:
                    spacing, plant_type, _ = main._plant_info(pid)
                except Exception:
                    spacing, plant_type = spacing_m, None
                mlat = alat + float(m.get("offset_y") or 0.0) / 111320
                mlng = alng + float(m.get("offset_x") or 0.0) / (111320 * cos_lat)
                main.map_widget.place_plant_marker(
                    pid, name, mlat, mlng, spacing_m=spacing,
                    plant_type=plant_type, color=member_color(m),
                    group_id=group_id, community_id=community_id)
                main._placed_plants.append({
                    "plant_id": pid, "common_name": name,
                    "lat": mlat, "lng": mlng,
                    "polyculture_name": poly_name,
                    "polyculture_center_lat": alat,
                    "polyculture_center_lng": alng,
                    "placement_group_id": group_id,
                })
                main._project["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [mlng, mlat]},
                    "properties": {
                        "element_type": "plant",
                        "plant_id": pid,
                        "common_name": name,
                        "polyculture_name": poly_name,
                        "polyculture_center_lat": alat,
                        "polyculture_center_lng": alng,
                        "placement_group_id": group_id,
                        "pattern_kind": "area_fill",
                        "quantity": 1,
                    },
                })
                batch.append((pid, name))

        try:
            main.plant_panel.on_plants_placed_batch(batch)
        except Exception:
            pass
        main._mark_modified()
        main._sync_planning_panel()
        main.statusBar().showMessage(
            f"Filled area — placed {len(anchors)} “{poly_name}” communities "
            f"({len(batch)} plants). Fine-tune by dragging or deleting.", 5000)
        return len(anchors)
