"""
shade.py — Cast-shade estimation for the design grid (V1.48; polygon V1.53).

Estimates which patches of ground are shaded a meaningful fraction of the day,
so the generator can put shade-tolerant plants where it is actually shady —
under existing trees, north of buildings, beneath the design's own canopy.

Casters are:
  * existing on-site trees / buildings the user marked (project features
    ``existing_tree`` / ``existing_building``),
  * user-drawn canopy / structure perimeters (``canopy_footprint``, or a
    ``custom_shape`` tagged ``cast_shade``) with a height attribute,
  * the design's own trees & shrubs (mature height + canopy), and
  * already-placed plants/structures.

The model is deliberately simple and **Qt-free**, reusing ``src/solar.py``:
for a handful of representative dates/times we get the sun's altitude/azimuth
and accumulate, per grid cell, the fraction of sampled daylight moments it lies
in shadow. Cells over a threshold are "shaded".

Two shadow geometries, selected at import time:
  * **Polygon (V1.53, preferred):** when ``shapely`` is installed, each caster's
    true 2D footprint is projected down-sun into a swept shadow polygon and the
    union is rasterized onto the grid (see ``src/shadow_geometry.py``).
  * **Circle (legacy fallback):** without shapely, each caster's shadow is a
    circle of its canopy radius displaced down-sun by ``height / tan(altitude)``.

Both share the same ``[[fraction]]`` grid contract, so ``src/zoning.py``,
``src/placement_score.py`` and the map overlay are unaffected by which path
runs. ``shapely`` is optional — headless installs / CI use the circle fallback.
Accurate enough to steer planting; not a ray-traced shadow study.

**Terrain self-shadowing (V1.55):** when the site's elevation grid carries real
relief, ``src/terrain_shade.py`` adds a per-moment DEM horizon mask (a ridge or
hillside shading ground down-sun) that is unioned with the footprint shadows
below — so a valley floor reads shady even with no caster nearby. Flat grids
yield no terrain mask, leaving the footprint-only result unchanged.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

try:
    from src import shadow_geometry
    _HAVE_SHAPELY = shadow_geometry._HAVE_SHAPELY
except ImportError:  # pragma: no cover - shadow_geometry is in-repo
    shadow_geometry = None
    _HAVE_SHAPELY = False

# Representative sampling — solstices + equinox capture the seasonal envelope;
# a few daylight hours capture the east→west sweep without a heavy loop.
_SAMPLE_MONTHS_DAYS = [(3, 20), (6, 21), (9, 22)]
_SAMPLE_HOURS_LOCAL = [9, 12, 15]          # mid-morning, noon, mid-afternoon
_MIN_SUN_ALT = 5.0                          # below this the sun casts no useful
                                            # shadow (and 1/tan blows up)
_MAX_SHADOW_M = 60.0                        # clamp absurd low-sun shadows


def _caster(lat: float, lng: float, height_m: float, radius_m: float,
            footprint: Optional[list] = None, kind: str = "building") -> dict:
    """A shade caster. ``footprint`` (a ring of ``(lng, lat)`` pairs), when
    present, is the true perimeter used by the shapely polygon path; the
    circle fallback always uses ``lat``/``lng`` + ``radius_m``. ``kind`` is
    ``"tree"`` (rounded crown that tapers — cast as a tapering canopy) or
    ``"building"`` (vertical extrusion of the footprint)."""
    c = {"lat": lat, "lng": lng, "height_m": max(0.0, float(height_m)),
         "radius_m": max(0.5, float(radius_m)), "kind": kind}
    if footprint:
        c["footprint"] = footprint
    return c


def casters_from_project(project_dict: dict) -> list[dict]:
    """Collect shade casters from a project FeatureCollection: marked existing
    trees/buildings plus already-placed plants/structures with a known height.
    Plant heights come from the catalogue (mature_height_meters / canopy)."""
    casters: list[dict] = []
    feats = (project_dict or {}).get("features") or []

    # Lazy plant lookup so this module stays import-light / DB-optional.
    def _plant_dims(pid):
        try:
            from src.db.plants import get_plant
            row = get_plant(pid) or {}
            h = row.get("mature_height_meters") or row.get("mature_height_m")
            cw = row.get("mature_canopy_m") or row.get("spacing_meters")
            return (float(h) if h else 0.0, float(cw) / 2 if cw else 0.5)
        except Exception:  # noqa: BLE001
            return (0.0, 0.5)

    for f in feats:
        props = f.get("properties", {}) or {}
        et = props.get("element_type")
        geom = f.get("geometry", {}) or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        # Point geometry → (lng, lat); polygon → centroid proxy + keep the ring
        # so the shapely path can cast the true footprint.
        ring = None
        if geom.get("type") == "Point":
            lng, lat = coords[0], coords[1]
        else:
            try:
                ring = coords[0]
                lng = sum(p[0] for p in ring) / len(ring)
                lat = sum(p[1] for p in ring) / len(ring)
            except Exception:  # noqa: BLE001
                continue
        # A footprint/canopy tagged caster_kind="tree" (or an existing_tree)
        # casts a tapering tree shadow; everything else extrudes as a building.
        kind = "tree" if props.get("caster_kind") == "tree" else "building"
        if et == "existing_tree":
            casters.append(_caster(lat, lng, props.get("height_m", 6.0),
                                   props.get("canopy_radius_m", 3.0),
                                   footprint=ring, kind="tree"))
        elif et == "existing_building":
            casters.append(_caster(lat, lng, props.get("height_m", 5.0),
                                   props.get("canopy_radius_m", 4.0),
                                   footprint=ring, kind="building"))
        elif et == "canopy_footprint":
            # User-drawn canopy/structure perimeter with a height attribute.
            h = props.get("height_m", 0.0)
            if h and h > 0:
                casters.append(_caster(lat, lng, h,
                                       props.get("canopy_radius_m", 3.0),
                                       footprint=ring, kind=kind))
        elif et == "custom_shape" and props.get("cast_shade"):
            # A generic drawn shape opted in as a shade caster.
            h = props.get("height_m", 0.0)
            if h and h > 0:
                casters.append(_caster(lat, lng, h,
                                       props.get("canopy_radius_m", 3.0),
                                       footprint=ring, kind=kind))
        elif et == "plant":
            pid = props.get("plant_id")
            h, r = _plant_dims(pid)
            if h >= 2.0:                      # only trees/large shrubs matter
                casters.append(_caster(lat, lng, h, r, kind="tree"))
    return casters


def _accumulate_shade(out, casters, sun, lat, lng, rows, cols, bbox,
                      terrain_elev=None) -> bool:
    """Add one sun-moment's shadow footprint into ``out`` (in place). Returns
    True when the sun was high enough to cast (so the caller can count valid
    samples). Shared by the season-averaged and single-instant entry points.

    Dispatches on shapely availability: the polygon path (preferred) casts the
    true footprints and rasterizes the union; the circle path is the legacy
    fallback used when shapely is absent (or the polygon path yields nothing).

    When ``terrain_elev`` (a real elevation grid dict) is supplied, terrain
    self-shadowing for this moment is unioned in alongside the footprint
    shadows, so a ridge / hillside shades cells even with no caster nearby
    (V1.55; ``src/terrain_shade.py``). It is ``None`` on flat sites, so the
    footprint-only behaviour is unchanged there."""
    if sun.altitude < _MIN_SUN_ALT:
        return False
    # Terrain self-shadow mask for this moment (caster-independent). None on a
    # flat grid / no elevation, so the footprint paths below are untouched there.
    tmask = None
    if terrain_elev is not None:
        try:
            from src import terrain_shade
            tmask = terrain_shade.terrain_shadow_mask(
                terrain_elev, sun.azimuth, sun.altitude)
        except Exception:  # noqa: BLE001 — terrain shadow is best-effort
            tmask = None
    # Polygon path only when there ARE casters; an empty caster list goes
    # straight to the circle helper, which applies the terrain mask alone
    # without calling shadow_geometry with no footprints.
    if casters and _HAVE_SHAPELY:
        elev = {"grid": out, "rows": rows, "cols": cols, "bbox": bbox}
        inc = shadow_geometry.shade_increment_for_moment(
            casters, elev, sun.azimuth, sun.altitude)
        if inc is not None:
            for r in range(rows):
                row_inc = inc[r]
                out_r = out[r]
                trow = tmask[r] if tmask is not None else None
                for c in range(cols):
                    if row_inc[c] or (trow is not None and trow[c]):
                        out_r[c] += 1.0
            return True
        # Polygon path produced nothing usable (e.g. degenerate footprints) —
        # fall through to the circle model so a marked caster still casts.
    return _accumulate_shade_circle(out, casters, sun, lat, lng, rows, cols,
                                    bbox, tmask=tmask)


def _tree_halfwidth(t: float, radius_m: float) -> float:
    """Tree-shadow half-width at fraction ``t`` along the base→tip segment: a
    thin trunk up to the crown base, ramping to the full canopy radius at the
    crown's widest point, then tapering to ~0 at the tip. Mirrors the silhouette
    of ``shadow_geometry.cast_tree_shadow`` for the raster fallback."""
    tf = getattr(shadow_geometry, "_TREE_TRUNK_FRAC", 0.30)
    cf = getattr(shadow_geometry, "_TREE_CROWN_FRAC", 0.65)
    tw = max(0.2, radius_m * getattr(shadow_geometry, "_TREE_TRUNK_W", 0.15))
    if t <= tf:
        return tw
    if t <= cf:
        return tw + (radius_m - tw) * (t - tf) / (cf - tf)
    return radius_m * (1.0 - (t - cf) / (1.0 - cf))


def _accumulate_shade_circle(out, casters, sun, lat, lng, rows, cols, bbox,
                             tmask=None) -> bool:
    """Capsule shadow model: each caster's shadow is the swept region — width =
    its canopy radius — from the caster's base to its down-sun tip displaced by
    ``height / tan(altitude)``. Used when shapely is unavailable, when the
    polygon path yields nothing, and for the terrain-only pass (empty caster
    list).

    Sweeping the whole base→tip segment (rather than parking a circle at the
    tip) matters at a low sun: the tip can fall off the grid, but the lit cells
    *between* the caster and the tip — what the user actually sees — still land
    inside the capsule, so evening / early-morning shadows no longer vanish.

    Casters and the terrain mask ``tmask`` (when given) are combined into a
    single per-moment boolean union, so a cell shaded by several casters and/or
    terrain still contributes at most 1.0 for the moment."""
    from src.solar import shadow_azimuth, shadow_length_factor
    if sun.altitude < _MIN_SUN_ALT:
        return False
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    shadow_dir = math.radians(shadow_azimuth(sun.azimuth))
    length_factor = shadow_length_factor(sun.altitude)

    def _cell_ll(r, c):
        t = r / max(1, rows - 1)
        u = c / max(1, cols - 1)
        return (bbox["north"] - t * (bbox["north"] - bbox["south"]),
                bbox["west"] + u * (bbox["east"] - bbox["west"]))

    moment = [[False] * cols for _ in range(rows)]
    for cv in casters:
        shadow_len = min(cv["height_m"] * length_factor, _MAX_SHADOW_M)
        radius_m = cv["radius_m"]
        is_tree = cv.get("kind") == "tree"
        # Down-sun tip offset from the caster, in metres. Azimuth is degrees
        # clockwise from north → north component = cos, east component = sin.
        tip_n = shadow_len * math.cos(shadow_dir)
        tip_e = shadow_len * math.sin(shadow_dir)
        seg_len2 = tip_n * tip_n + tip_e * tip_e
        r2 = radius_m * radius_m
        for r in range(rows):
            for c in range(cols):
                clat, clng = _cell_ll(r, c)
                # Cell offset from the caster, in metres.
                pe = (clng - cv["lng"]) * 111320.0 * cos_lat
                pn = (clat - cv["lat"]) * 111320.0
                # Project onto the base→tip segment (t clamped to [0,1]).
                if seg_len2 <= 1e-9:
                    t = 0.0
                else:
                    t = (pe * tip_e + pn * tip_n) / seg_len2
                    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                de = pe - t * tip_e
                dn = pn - t * tip_n
                d2 = de * de + dn * dn
                # A building is a constant-radius capsule; a tree tapers — thin
                # trunk near the base, full radius at the crown, → 0 at the tip.
                if is_tree:
                    w = _tree_halfwidth(t, radius_m)
                    shaded = d2 <= w * w
                else:
                    shaded = d2 <= r2
                if shaded:
                    moment[r][c] = True
    if tmask is not None:
        for r in range(rows):
            trow = tmask[r]
            mrow = moment[r]
            for c in range(cols):
                if trow[c]:
                    mrow[c] = True
    for r in range(rows):
        out_r = out[r]
        mrow = moment[r]
        for c in range(cols):
            if mrow[c]:
                out_r[c] += 1.0
    return True


def _terrain_elev_or_none(elev: dict):
    """Return ``elev`` when it carries enough vertical relief for terrain
    self-shadowing to matter, else ``None`` — flat sites then keep the
    footprint-only behaviour bit-for-bit. Cheap min/max scan via
    ``terrain_shade.has_relief``; degrades to ``None`` if that import fails."""
    try:
        from src import terrain_shade
        return elev if terrain_shade.has_relief(elev) else None
    except Exception:  # noqa: BLE001 — terrain shadow is best-effort
        return None


def shade_grid(casters: list[dict], elev: dict,
               lat: Optional[float] = None,
               lng: Optional[float] = None,
               dates: Optional[list] = None,
               hours: Optional[list] = None,
               terrain: bool = True) -> list[list[float]]:
    """``[[fraction]]`` grid (same shape as ``elev['grid']``): per cell, the
    fraction of sampled daylight moments it is shaded by any caster or (when
    the grid carries relief) by upwind terrain.

    ``dates`` is a list of ``(month, day)`` and ``hours`` a list of local solar
    hours; both default to the season/day-spread sample (equinox + solstices ×
    morning/noon/afternoon) — the season-averaged shade used for placement.
    ``lat``/``lng`` default to the grid-bbox centre. ``terrain`` enables the DEM
    self-shadowing pass (``src/terrain_shade.py``); a no-op on flat grids."""
    grid = elev.get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    out = [[0.0] * cols for _ in range(rows)]
    if rows == 0 or cols == 0:
        return out
    # Terrain self-shadowing can shade cells with no nearby caster (a valley
    # floor, the lee of a ridge), so only bail when there is NEITHER a caster
    # NOR usable terrain relief. Flat grids → terrain_elev None → the
    # footprint-only result is identical to pre-V1.55.
    terrain_elev = _terrain_elev_or_none(elev) if terrain else None
    if not casters and terrain_elev is None:
        return out

    bbox = elev["bbox"]
    if lat is None:
        lat = (bbox["north"] + bbox["south"]) / 2.0
    if lng is None:
        lng = (bbox["east"] + bbox["west"]) / 2.0

    dates = dates or _SAMPLE_MONTHS_DAYS
    hours = hours or _SAMPLE_HOURS_LOCAL

    from src.solar import sun_position
    samples = 0
    for mo, day in dates:
        for hr in hours:
            # solar.sun_position expects UTC and adds lng/15 back to recover
            # local solar time, so convert the local sample hour to UTC first
            # (utc = local - lng/15). Without this, noon would read as dawn.
            dt = datetime(2025, mo, day) + timedelta(hours=hr - lng / 15.0)
            if _accumulate_shade(out, casters, sun_position(lat, lng, dt),
                                 lat, lng, rows, cols, bbox,
                                 terrain_elev=terrain_elev):
                samples += 1

    if samples:
        for r in range(rows):
            for c in range(cols):
                out[r][c] = min(1.0, out[r][c] / samples)
    return out


def shade_grid_at(casters: list[dict], elev: dict, when: datetime,
                  lat: Optional[float] = None,
                  lng: Optional[float] = None,
                  terrain: bool = True) -> list[list[float]]:
    """Binary shade grid for a single instant ``when`` (a naive *local* solar
    datetime): 1.0 where shaded, 0.0 where lit. Used by the time-of-day overlay
    slider so the user can watch shadows sweep across the day/season.
    ``terrain`` unions in the DEM self-shadow for the instant (no-op on flat
    grids)."""
    grid = elev.get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    out = [[0.0] * cols for _ in range(rows)]
    if rows == 0 or cols == 0:
        return out
    terrain_elev = _terrain_elev_or_none(elev) if terrain else None
    if not casters and terrain_elev is None:
        return out
    bbox = elev["bbox"]
    if lat is None:
        lat = (bbox["north"] + bbox["south"]) / 2.0
    if lng is None:
        lng = (bbox["east"] + bbox["west"]) / 2.0
    from src.solar import sun_position
    dt_utc = when + timedelta(hours=-lng / 15.0)
    _accumulate_shade(out, casters, sun_position(lat, lng, dt_utc),
                      lat, lng, rows, cols, bbox, terrain_elev=terrain_elev)
    return out


def shade_grid_for_design(project_dict: dict, elev: dict,
                          extra_casters: Optional[list] = None,
                          when: Optional[datetime] = None,
                          terrain: bool = True
                          ) -> list[list[float]]:
    """Convenience wrapper: gather casters from the project (existing + placed)
    plus any ``extra_casters`` and compute the shade grid over ``elev``. With
    ``when`` set, returns the single-instant grid; otherwise the season-average.
    ``terrain`` toggles the DEM self-shadowing pass (default on)."""
    casters = casters_from_project(project_dict)
    if extra_casters:
        casters = casters + list(extra_casters)
    if when is not None:
        return shade_grid_at(casters, elev, when, terrain=terrain)
    return shade_grid(casters, elev, terrain=terrain)


# Shade colour ramp: translucent indigo that deepens with shade fraction.
# (upper-bound fraction, (r, g, b, a)) — first bucket whose bound exceeds the
# value wins. Fully-lit cells are transparent so only shade shows.
_SHADE_RAMP = [
    (0.15, (0, 0, 0, 0)),         # essentially lit → transparent
    (0.40, (63, 81, 181, 60)),   # light shade
    (0.70, (48, 63, 159, 110)),  # moderate
    (1.01, (26, 35, 126, 160)),  # deep shade
]


def _shade_to_rgba(frac: float) -> tuple[int, int, int, int]:
    for upper, rgba in _SHADE_RAMP:
        if frac < upper:
            return rgba
    return _SHADE_RAMP[-1][1]


def shade_ramp_rgba(shade_grid_vals: list[list[float]]) -> tuple[bytes, int, int]:
    """Convert a shade fraction grid to row-major RGBA bytes (mirrors
    ``terrain.slope_ramp_rgba``), ready for ``terrain.encode_png_rgba`` and the
    map's image overlay."""
    h = len(shade_grid_vals)
    w = len(shade_grid_vals[0]) if h else 0
    out = bytearray(w * h * 4)
    for y, row in enumerate(shade_grid_vals):
        for x, frac in enumerate(row):
            r, g, b, a = _shade_to_rgba(frac)
            i = (y * w + x) * 4
            out[i] = r
            out[i + 1] = g
            out[i + 2] = b
            out[i + 3] = a
    return bytes(out), w, h


def shade_overlay_payload(project_dict: dict, boundary, site_config,
                          when: Optional[datetime] = None) -> Optional[dict]:
    """Qt-free orchestration for the shade map overlay (called by the GUI's
    ShadeWorker off-thread). Builds the elevation grid for the site, computes
    the shade grid (single-instant when ``when`` is given, else season-average),
    encodes it to a PNG data URL, and returns ``{"data_url", "bbox"}`` for
    ``map_widget.draw_shade_overlay``. ``None`` when no grid/casters are
    available (caller shows "no shade to display")."""
    try:
        from src import zoning, terrain
        elev = zoning.site_elevation_grid(boundary, site_config)
        if not elev:
            return None
        grid = shade_grid_for_design(project_dict, elev, when=when)
        # All-zero (no casters / nothing shaded) → nothing to draw.
        if not any(v > 0 for row in grid for v in row):
            return None
        rgba, w, h = shade_ramp_rgba(grid)
        png = terrain.encode_png_rgba(rgba, w, h)
        import base64
        data_url = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        b = elev["bbox"]
        return {"data_url": data_url,
                "bbox": {"south": b["south"], "north": b["north"],
                         "west": b["west"], "east": b["east"]}}
    except Exception:  # noqa: BLE001 — overlay is best-effort
        return None


def _casters_extent_bbox(casters: list) -> Optional[dict]:
    """South/north/west/east envelope of every caster (footprint vertices or the
    point lat/lng). Anchors the metric origin for the vector path without needing
    a DEM grid."""
    lats: list = []
    lngs: list = []
    for cv in casters:
        ring = cv.get("footprint")
        if ring:
            for p in ring:
                lngs.append(p[0])
                lats.append(p[1])
        else:
            lats.append(cv["lat"])
            lngs.append(cv["lng"])
    if not lats:
        return None
    return {"south": min(lats), "north": max(lats),
            "west": min(lngs), "east": max(lngs)}


def shadow_polygons_payload(project_dict: dict, boundary, site_config,
                            when: Optional[datetime] = None) -> Optional[dict]:
    """Qt-free: build true-shape shadow polygons (lat/lng) for the map's vector
    overlay — crisp, real-shape shadows at any zoom, decoupled from the coarse
    elevation grid (which can drop a small building's short noon shadow).

    With ``when`` set the shadows are for that *exact instant*; with ``when=None``
    (Typical) they are the union of every season/day sample moment — the
    "ever-shaded" envelope. Returns ``{"polygons": [...], "bbox": {...}}`` where
    each polygon is a list of rings (exterior first, then holes) of ``[lat, lng]``
    pairs for ``map_widget.draw_shadow_polygons``. ``None`` when shapely is
    unavailable, no casters cast a shadow, or no site origin is known — the caller
    then falls back to the grid/PNG overlay."""
    if not _HAVE_SHAPELY:
        return None
    try:
        casters = casters_from_project(project_dict)
        casters = [c for c in casters if c.get("height_m", 0.0) > 0]
        if not casters:
            return None

        bbox = _casters_extent_bbox(casters)
        if bbox is None:
            return None
        origin = shadow_geometry.origin_for_bbox(bbox)

        # Build metric casters once; reuse across every sun moment. Buildings
        # extrude their footprint vertically; trees have a rounded crown that
        # tapers, so they're cast per-moment from their centre + radius via
        # cast_tree_shadow.
        metric_buildings: list = []     # (poly, height_m)
        metric_trees: list = []         # (center_xy, radius_m, height_m)
        for cv in casters:
            if cv.get("kind") == "tree":
                xy = origin.to_xy(cv["lng"], cv["lat"])
                metric_trees.append(
                    (xy, cv.get("radius_m", 3.0), cv["height_m"]))
                continue
            ring = cv.get("footprint")
            poly = None
            if ring:
                poly = shadow_geometry.footprint_to_metric(ring, origin)
            if poly is None or poly.is_empty:
                # No ring, or a degenerate ring shapely couldn't repair — keep
                # the caster by falling back to its radius circle instead of
                # dropping it, so a building never silently casts nothing.
                poly = shadow_geometry.point_footprint_metric(
                    cv["lng"], cv["lat"], cv.get("radius_m", 0.5), origin)
            if poly is not None and not poly.is_empty:
                metric_buildings.append((poly, cv["height_m"]))
        if not metric_buildings and not metric_trees:
            return None

        from src.solar import sun_position
        clat = (bbox["north"] + bbox["south"]) / 2.0
        clng = (bbox["east"] + bbox["west"]) / 2.0

        moments: list = []
        if when is not None:
            moments.append(when)
        else:
            for mo, day in _SAMPLE_MONTHS_DAYS:
                for hr in _SAMPLE_HOURS_LOCAL:
                    moments.append(datetime(2025, mo, day) + timedelta(hours=hr))

        shadows: list = []
        for local_dt in moments:
            # sun_position expects UTC and re-derives local solar time from lng.
            dt_utc = local_dt + timedelta(hours=-clng / 15.0)
            sun = sun_position(clat, clng, dt_utc)
            if sun.altitude < _MIN_SUN_ALT:
                continue
            if metric_buildings:
                g = shadow_geometry.union_shadows(
                    metric_buildings, sun.azimuth, sun.altitude)
                if g is not None and not g.is_empty:
                    shadows.append(g)
            for xy, rad, h in metric_trees:
                tg = shadow_geometry.cast_tree_shadow(
                    xy, rad, h, sun.azimuth, sun.altitude)
                if tg is not None and not tg.is_empty:
                    shadows.append(tg)
        if not shadows:
            return None

        merged = shadow_geometry.union_geometries(shadows)
        polygons = shadow_geometry.latlng_rings(merged, origin)
        if not polygons:
            return None

        # Envelope of the drawn shadows (for fit/debug; vector layer needs no bbox).
        all_lat = [pt[0] for poly in polygons for ring in poly for pt in ring]
        all_lng = [pt[1] for poly in polygons for ring in poly for pt in ring]
        out_bbox = {"south": min(all_lat), "north": max(all_lat),
                    "west": min(all_lng), "east": max(all_lng)}
        return {"polygons": polygons, "bbox": out_bbox}
    except Exception:  # noqa: BLE001 — overlay is best-effort
        return None


def classify_zone_tags(project_dict: dict, boundary, site_config
                       ) -> Optional[list]:
    """Qt-free: compute the season-average shade grid for the site and turn each
    cell into a shade-tag row for the SQLite cache (``src/db/shade_zones.py``).

    Returns a list of dicts ``{zone_id, shade_tag, shade_frac, centroid_lat,
    centroid_lng}`` (one per grid cell, ``zone_id = "r{r}c{c}"``), or ``None``
    when no elevation grid is available. The tag mapping lives in
    ``shade_zones.tag_for_fraction`` so it stays the single source of truth.
    Geometry is NOT returned — only the derived per-cell tag and its centroid —
    keeping project geometry out of the global DB per CLAUDE.md."""
    try:
        from src import zoning
        from src.db.shade_zones import tag_for_fraction
        elev = zoning.site_elevation_grid(boundary, site_config)
        if not elev:
            return None
        grid = shade_grid_for_design(project_dict, elev)   # season average
        rows = elev.get("rows", len(grid))
        cols = elev.get("cols", len(grid[0]) if grid else 0)
        out: list = []
        for r in range(rows):
            for c in range(cols):
                frac = grid[r][c]
                clat, clng = zoning.cell_latlng(elev, r, c)
                out.append({
                    "zone_id": f"r{r}c{c}",
                    "shade_tag": tag_for_fraction(frac),
                    "shade_frac": frac,
                    "centroid_lat": clat,
                    "centroid_lng": clng,
                })
        return out
    except Exception:  # noqa: BLE001 — classification is best-effort
        return None


# ── Qt worker thread (optional; mirrors terrain.TerrainWorker) ───────────────
# Defined only when PyQt6 is importable, so the pure compute above stays usable
# (and testable) without Qt. The GUI runs shade_overlay_payload off the UI
# thread because it can trigger a network elevation fetch.
try:
    from PyQt6.QtCore import QObject, pyqtSignal
    _HAVE_QT = True
except ImportError:
    _HAVE_QT = False

if _HAVE_QT:
    class ShadeWorker(QObject):
        """Compute the shade overlay payload off the UI thread.

            worker = ShadeWorker(project_dict, boundary, site_config, when)
            worker.moveToThread(thread); worker.ready.connect(on_ready)
            thread.started.connect(worker.run); thread.start()
        """

        ready = pyqtSignal(object)   # payload dict, or None
        finished = pyqtSignal()

        def __init__(self, project_dict, boundary, site_config, when=None,
                     parent=None):
            super().__init__(parent)
            self._project = project_dict
            self._boundary = boundary
            self._site_config = site_config
            self._when = when

        def run(self):
            try:
                payload = shade_overlay_payload(
                    self._project, self._boundary, self._site_config, self._when)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                payload = None
            self.ready.emit(payload)
            self.finished.emit()

    class ShadowPolygonWorker(QObject):
        """Compute the true-shape vector shadow payload off the UI thread.
        Mirrors ShadeWorker; emits the ``shadow_polygons_payload`` result (or
        None) so the caller can fall back to the grid/PNG overlay."""

        ready = pyqtSignal(object)   # {"polygons", "bbox"} dict, or None
        finished = pyqtSignal()

        def __init__(self, project_dict, boundary, site_config, when=None,
                     parent=None):
            super().__init__(parent)
            self._project = project_dict
            self._boundary = boundary
            self._site_config = site_config
            self._when = when

        def run(self):
            try:
                payload = shadow_polygons_payload(
                    self._project, self._boundary, self._site_config, self._when)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                payload = None
            self.ready.emit(payload)
            self.finished.emit()

    class ShadeZoneWorker(QObject):
        """Classify planting zones (full sun / partial / full shade) off the UI
        thread. Mirrors ShadeWorker — the elevation fetch can be slow.

            worker = ShadeZoneWorker(project_dict, boundary, site_config)
            worker.moveToThread(thread); worker.ready.connect(on_ready)
            thread.started.connect(worker.run); thread.start()

        ``ready`` carries the list of tag rows (or None) for the caller to
        persist via ``src/db/shade_zones.py``."""

        ready = pyqtSignal(object)   # list[row] dicts, or None
        finished = pyqtSignal()

        def __init__(self, project_dict, boundary, site_config, parent=None):
            super().__init__(parent)
            self._project = project_dict
            self._boundary = boundary
            self._site_config = site_config

        def run(self):
            try:
                rows = classify_zone_tags(
                    self._project, self._boundary, self._site_config)
            except Exception:  # noqa: BLE001 — never crash the worker thread
                rows = None
            self.ready.emit(rows)
            self.finished.emit()
