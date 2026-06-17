"""
src/controllers/area_fill_controller.py — place a polygon fill (N3′).

Turns the pure ``area_fill.plan_fill`` output into placed plants through the
ProjectStore single write path (``src/project_store.py``) plus a shared
placement group, so rendering, undo-as-a-unit, the habitat score and the cost
readout all work on a filled area exactly as they do for a generated or
hand-placed design.
"""

from __future__ import annotations

from src import area_fill
from src.project_store import store_for


class AreaFillController:
    def __init__(self, main):
        self._main = main

    def fill(self, ring, member_specs, spacing_m: float,
             poly_name: str = "", jitter: float = 0.0, rng=None,
             matrix: bool = False) -> int:
        """Fill a polygon ``ring`` (``[lng, lat]`` pairs) with plants.

        ``member_specs`` is ``[(plant_id, weight), ...]`` — one entry for a single
        species, or a community's members (equal weights by default). With
        ``matrix=True`` the ground-layer species (grasses / groundcovers) become a
        connective matrix and the taller species scatter through it (Rainer/West,
        P2); with no ground-layer species it falls back to an even fill. Returns
        the number of plants placed. All share one group id so the fill deletes as
        a unit."""
        member_specs = [(int(pid), float(w)) for pid, w in (member_specs or [])
                        if pid is not None]
        records = None
        if matrix:
            records = self._matrix_records(ring, member_specs, spacing_m, jitter, rng)
        if records is None:
            records = area_fill.plan_fill(ring, member_specs, spacing_m, jitter, rng)
        n = self._place_plant_records(records, poly_name=poly_name)
        if n:
            self._main.statusBar().showMessage(
                f"Filled area — placed {n} plants"
                + (" as a matrix" if matrix and records is not None else "")
                + (f" from “{poly_name}”" if poly_name else "")
                + ". Fine-tune by dragging or deleting.", 5000)
        return n

    def _typed_member(self, pid, weight=1.0, layer_bucket=None) -> dict:
        """Build a planting_spacing record for a plant id (type + spread habit +
        canopy), for the layered fill engine."""
        rec = {}
        try:
            from src.db.plants import get_plant
            rec = get_plant(int(pid)) or {}
        except Exception:  # noqa: BLE001
            rec = {}
        tm = {
            "plant_id": int(pid),
            "plant_type": rec.get("plant_type") or "",
            "spread_habit": rec.get("spread_habit") or "",
            "mature_canopy_m": rec.get("mature_canopy_m"),
            "weight": float(weight or 1.0),
        }
        if layer_bucket:
            tm["layer_bucket"] = layer_bucket
        return tm

    def _matrix_records(self, ring, member_specs, spacing_m, jitter, rng):
        """Per-type, spread-aware matrix fill from a plant mix: each layer at its
        own spacing (trees widest … groundcover knitting the rest), driven by the
        base spacing spinner (F22/F35). Returns records, or None when empty."""
        if not member_specs:
            return None
        from src import planting_spacing
        typed = [self._typed_member(pid, w) for pid, w in member_specs]
        return planting_spacing.layered_fill_plan(
            ring, typed, spacing_m, rng=rng, jitter=jitter or 0.6)

    def _place_plant_records(self, records, *, poly_name: str = "") -> int:
        """Place ``(plant_id, lat, lng)`` records as plants through the single
        write path, under one shared placement group. Returns the count."""
        if not records:
            return 0
        main = self._main
        import src.project as project_io
        group_id = project_io.new_placement_group_id()
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
                spacing, plant_type = 1.0, None
            community_id = project_io.community_id_for(lat, lng)
            main.map_widget.place_plant_marker(
                pid, name, lat, lng, spacing_m=spacing, plant_type=plant_type,
                color=None, group_id=group_id, community_id=community_id)
            store_for(main).add_plant(
                pid, name, lat, lng, placement_group_id=group_id,
                polyculture_name=poly_name, pattern_kind="area_fill")
            batch.append((pid, name))

        try:
            main.plant_panel.on_plants_placed_batch(batch)
        except Exception:
            pass
        main._mark_modified()
        main._sync_planning_panel()
        return len(batch)

    def _fill_community_matrix(self, ring, polyculture, spacing_m, rng):
        """Matrix-plant a community via the layered engine: each member placed by
        its vegetation layer at the right spacing — groundcover knits the ground
        while taller members stand distinct (instead of stamping whole units).
        Returns the plant count, or None when the community has no ground layer to
        knit with (the caller then falls back to unit stamping)."""
        from src import planting_spacing
        members = (polyculture or {}).get("members") or []
        typed, ground_sps = [], []
        for m in members:
            try:
                pid = int(m["plant_id"])
            except Exception:  # noqa: BLE001
                continue
            bucket = planting_spacing.bucket_for_member(m)
            typed.append(self._typed_member(pid, m.get("weight") or 1.0,
                                            layer_bucket=bucket))
            if bucket == "ground":
                ground_sps.append(float(m.get("spacing_m") or 0))
        has_ground = any(t.get("layer_bucket") == "ground" for t in typed)
        has_taller = any(t.get("layer_bucket") != "ground" for t in typed)
        if not typed or not (has_ground and has_taller):
            return None
        # Base = the groundcover members' real spacing (denser than the unit cell
        # spacing the spinner provides), clamped to a sensible band.
        gsp = [s for s in ground_sps if s > 0]
        base = max(0.3, min(1.5, min(gsp) if gsp else 0.6))
        records = planting_spacing.layered_fill_plan(ring, typed, base, rng=rng)
        n = self._place_plant_records(records, poly_name=polyculture.get("name", ""))
        if n:
            self._main.statusBar().showMessage(
                f"Filled area — matrix planting of “{polyculture.get('name', '')}” "
                f"({n} plants): ground layer knit together, taller plants spaced "
                "by type.", 5000)
        return n

    def _fill_community_mix_matrix(self, ring, communities, spacing_m, rng):
        """Matrix-plant a MIX of communities via the layered engine: pool every
        member of every community (weighted by the community's mix weight), then
        place them by vegetation layer — groundcover knits the ground while taller
        members stand distinct — over the whole area (instead of stamping each
        community as a separate unit). Returns the plant count, or None when the
        pooled members have no ground layer to knit with (caller falls back)."""
        from src import planting_spacing
        pooled: dict = {}   # (plant_id, bucket) -> typed member (weights summed)
        ground_sps: list = []
        for c in communities:
            cw = max(0.0, float(c.get("weight") or 1.0))
            for m in (c.get("polyculture") or {}).get("members") or []:
                try:
                    pid = int(m["plant_id"])
                except Exception:  # noqa: BLE001
                    continue
                bucket = planting_spacing.bucket_for_member(m)
                w = cw * float(m.get("weight") or 1.0)
                key = (pid, bucket)
                if key in pooled:
                    pooled[key]["weight"] += w
                else:
                    pooled[key] = self._typed_member(pid, w, layer_bucket=bucket)
                if bucket == "ground":
                    ground_sps.append(float(m.get("spacing_m") or 0))
        typed = list(pooled.values())
        has_ground = any(t.get("layer_bucket") == "ground" for t in typed)
        has_taller = any(t.get("layer_bucket") != "ground" for t in typed)
        if not typed or not (has_ground and has_taller):
            return None
        gsp = [s for s in ground_sps if s > 0]
        base = max(0.3, min(1.5, min(gsp) if gsp else 0.6))
        records = planting_spacing.layered_fill_plan(ring, typed, base, rng=rng)
        n = self._place_plant_records(records, poly_name="Community mix")
        if n:
            self._main.statusBar().showMessage(
                f"Filled area — matrix planting of a {len(communities)}-community "
                f"mix ({n} plants): ground layer knit together, taller plants "
                "spaced by type.", 5000)
        return n

    def fill_communities(self, ring, polyculture: dict, spacing_m: float,
                         rng=None, matrix: bool = False) -> int:
        """Fill a polygon with whole community UNITS — each anchor expands every
        member at its designed ``offset_x``/``offset_y``, exactly like a single
        community placement — rather than scattering individual member plants.

        With ``matrix=True`` the community is instead dissolved into matrix
        planting (groundcover layer knits the ground, taller layers scatter), per
        :meth:`_fill_community_matrix`; it falls back to unit stamping when the
        community has no ground layer.

        Anchors sit on a hex grid stepped by the community's natural footprint
        diameter plus ``spacing_m`` (the Communities tab's cell spacing, here the
        gap *between* units). Returns the number of community units placed. All
        units share one placement group so the fill deletes as a unit."""
        import math
        from src.db.polycultures import community_natural_radius

        members = (polyculture or {}).get("members") or []
        if not members:
            return 0
        if matrix:
            n = self._fill_community_matrix(ring, polyculture, spacing_m, rng)
            if n is not None:
                return n
            # No ground layer to knit with — fall through to unit stamping.
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

        import src.project as project_io
        group_id = project_io.new_placement_group_id()
        units = [(alat, alng, polyculture) for alat, alng in anchors]
        n_plants = self._place_community_units(units, group_id)

        self._finish_fill(n_plants)
        self._main.statusBar().showMessage(
            f"Filled area — placed {len(anchors)} “{polyculture.get('name','')}” "
            f"communities ({n_plants} plants). Fine-tune by dragging or deleting.",
            5000)
        return len(anchors)

    def fill_community_mix(self, ring, communities: list, spacing_m: float,
                           rng=None, matrix: bool = False) -> int:
        """Fill a polygon with whole community units drawn from a MIX of
        communities (each ``{id, weight, name, polyculture}``). Units sit on a
        grid stepped by the largest community's footprint + ``spacing_m``; which
        community lands on each anchor is chosen by weight and then spread so the
        same community isn't clumped — the same even distribution as a Circle-fill
        mix. Returns the number of community units placed (one shared group).

        With ``matrix=True`` the whole mix instead dissolves into a single matrix
        planting — every member of every community pooled (weighted by the
        community's mix weight), the ground layer knitting the area while taller
        plants scatter through it (:meth:`_fill_community_mix_matrix`); it falls
        back to unit stamping when the pooled members have no ground layer."""
        import math
        from src.db.polycultures import community_natural_radius

        communities = [c for c in (communities or [])
                       if (c.get("polyculture") or {}).get("members")]
        if not communities:
            return 0
        if matrix:
            n = self._fill_community_mix_matrix(ring, communities, spacing_m, rng)
            if n is not None:
                return n
            # No ground layer to knit with — fall through to unit stamping.
        max_radius = max(community_natural_radius(c["polyculture"])
                         for c in communities)
        step = 2.0 * max_radius + max(0.0, float(spacing_m or 0.0))
        anchors = area_fill.fill_points(ring, step, 0.0, rng)
        if not anchors:
            from src.osm_features import ring_centroid
            from src.geometry import point_in_ring
            c = ring_centroid(ring)
            if c is not None and point_in_ring(c[0], c[1], ring):
                anchors = [(c[0], c[1])]
            else:
                return 0

        # Choose a community per anchor by weight, spread evenly (treat each
        # community as a "species" for the shared assigner + repulsion optimiser).
        from src.polyculture import assign_species, optimize_layout
        species = [{"id": int(c["id"]), "weight": max(0.0, float(c.get("weight") or 1))}
                   for c in communities]
        positions = [(a[0], a[1]) for a in anchors]
        assigns = assign_species(positions, species, "even_split")
        try:
            assigns = optimize_layout(positions, assigns)
        except Exception:  # noqa: BLE001
            pass
        poly_by_id = {int(c["id"]): c["polyculture"] for c in communities}

        import src.project as project_io
        group_id = project_io.new_placement_group_id()
        units = [(positions[i][0], positions[i][1],
                  poly_by_id[int(assigns[i]["id"])])
                 for i in range(len(positions))]
        n_plants = self._place_community_units(units, group_id)

        self._finish_fill(n_plants)
        self._main.statusBar().showMessage(
            f"Filled area — placed {len(anchors)} community units from a "
            f"{len(communities)}-community mix ({n_plants} plants).", 5000)
        return len(anchors)

    # ── shared placement bookkeeping ─────────────────────────────────────────

    def _place_community_units(self, units, group_id, *,
                               pattern_kind: str = "area_fill") -> int:
        """Place a list of ``(anchor_lat, anchor_lng, polyculture)`` community
        units, expanding each member at its offset. Returns the plant count.

        Also the engine behind community-as-pattern placement (Row / Grid /
        Circle of communities) — those call sites pass their own
        ``pattern_kind`` so the feature records how the plant was placed."""
        import math
        import src.project as project_io
        from src.member_colors import member_color
        main = self._main
        batch: list = []
        for alat, alng, poly in units:
            poly_name = (poly or {}).get("name", "")
            community_id = project_io.community_id_for(alat, alng)
            cos_lat = math.cos(alat * math.pi / 180) or 1e-9
            for m in (poly.get("members") or []):
                pid = m["plant_id"]
                name = m.get("common_name", "") or f"Plant #{pid}"
                try:
                    spacing, plant_type, _ = main._plant_info(pid)
                except Exception:
                    spacing, plant_type = 1.0, None
                mlat = alat + float(m.get("offset_y") or 0.0) / 111320
                mlng = alng + float(m.get("offset_x") or 0.0) / (111320 * cos_lat)
                main.map_widget.place_plant_marker(
                    pid, name, mlat, mlng, spacing_m=spacing,
                    plant_type=plant_type, color=member_color(m),
                    group_id=group_id, community_id=community_id)
                store_for(main).add_plant(
                    pid, name, mlat, mlng, placement_group_id=group_id,
                    polyculture_name=poly_name,
                    polyculture_center_lat=alat,
                    polyculture_center_lng=alng,
                    pattern_kind=pattern_kind)
                batch.append((pid, name))
        try:
            main.plant_panel.on_plants_placed_batch(batch)
        except Exception:
            pass
        return len(batch)

    def _finish_fill(self, _n_plants) -> None:
        self._main._mark_modified()
        self._main._sync_planning_panel()
