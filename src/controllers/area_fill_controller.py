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
