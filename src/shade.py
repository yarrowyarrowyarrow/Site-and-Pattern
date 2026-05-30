"""
shade.py — Cast-shade estimation for the design grid (V1.48).

Estimates which patches of ground are shaded a meaningful fraction of the day,
so the generator can put shade-tolerant plants where it is actually shady —
under existing trees, north of buildings, beneath the design's own canopy.

Casters are:
  * existing on-site trees / buildings the user marked (project features
    ``existing_tree`` / ``existing_building``),
  * the design's own trees & shrubs (mature height + canopy), and
  * already-placed plants/structures.

The model is deliberately simple and **Qt-free**, reusing ``src/solar.py``:
for a handful of representative dates/times we get the sun's altitude/azimuth,
project each caster's shadow as a circle of the caster's canopy radius displaced
down-sun by ``height / tan(altitude)``, and accumulate, per grid cell, the
fraction of sampled daylight moments it lies in shadow. Cells over a threshold
are "shaded". Accurate enough to steer planting; not a ray-traced shadow study.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

# Representative sampling — solstices + equinox capture the seasonal envelope;
# a few daylight hours capture the east→west sweep without a heavy loop.
_SAMPLE_MONTHS_DAYS = [(3, 20), (6, 21), (9, 22)]
_SAMPLE_HOURS_LOCAL = [9, 12, 15]          # mid-morning, noon, mid-afternoon
_MIN_SUN_ALT = 5.0                          # below this the sun casts no useful
                                            # shadow (and 1/tan blows up)
_MAX_SHADOW_M = 60.0                        # clamp absurd low-sun shadows


def _caster(lat: float, lng: float, height_m: float, radius_m: float) -> dict:
    return {"lat": lat, "lng": lng, "height_m": max(0.0, float(height_m)),
            "radius_m": max(0.5, float(radius_m))}


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
        # Point geometry → (lng, lat); polygon → use first vertex as a proxy.
        if geom.get("type") == "Point":
            lng, lat = coords[0], coords[1]
        else:
            try:
                ring = coords[0]
                lng = sum(p[0] for p in ring) / len(ring)
                lat = sum(p[1] for p in ring) / len(ring)
            except Exception:  # noqa: BLE001
                continue
        if et == "existing_tree":
            casters.append(_caster(lat, lng, props.get("height_m", 6.0),
                                   props.get("canopy_radius_m", 3.0)))
        elif et == "existing_building":
            casters.append(_caster(lat, lng, props.get("height_m", 5.0),
                                   props.get("canopy_radius_m", 4.0)))
        elif et == "plant":
            pid = props.get("plant_id")
            h, r = _plant_dims(pid)
            if h >= 2.0:                      # only trees/large shrubs matter
                casters.append(_caster(lat, lng, h, r))
    return casters


def shade_grid(casters: list[dict], elev: dict,
               lat: Optional[float] = None,
               lng: Optional[float] = None) -> list[list[float]]:
    """Return a ``[[fraction]]`` grid (same shape as ``elev['grid']``) giving,
    per cell, the fraction of sampled daylight moments the cell is shaded by any
    caster. ``lat``/``lng`` default to the grid-bbox centre (sun position barely
    varies across a single property). Empty/zero grid when there are no casters."""
    grid = elev.get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    out = [[0.0] * cols for _ in range(rows)]
    if not casters or rows == 0 or cols == 0:
        return out

    bbox = elev["bbox"]
    if lat is None:
        lat = (bbox["north"] + bbox["south"]) / 2.0
    if lng is None:
        lng = (bbox["east"] + bbox["west"]) / 2.0
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9

    from src.solar import sun_position, shadow_azimuth, shadow_length_factor

    # Precompute cell centres once.
    def _cell_ll(r, c):
        t = r / max(1, rows - 1)
        u = c / max(1, cols - 1)
        return (bbox["north"] - t * (bbox["north"] - bbox["south"]),
                bbox["west"] + u * (bbox["east"] - bbox["west"]))

    samples = 0
    for mo, day in _SAMPLE_MONTHS_DAYS:
        for hr in _SAMPLE_HOURS_LOCAL:
            # solar.sun_position expects a UTC datetime and adds lng/15 back to
            # recover local solar time, so convert our local sample hour to UTC
            # first (utc = local - lng/15). Without this, noon reads as dawn.
            utc_hour = hr - lng / 15.0
            dt = datetime(2025, mo, day) + timedelta(hours=utc_hour)
            sun = sun_position(lat, lng, dt)
            if sun.altitude < _MIN_SUN_ALT:
                continue
            samples += 1
            shadow_dir = math.radians(shadow_azimuth(sun.azimuth))
            length_factor = shadow_length_factor(sun.altitude)
            for cv in casters:
                shadow_len = min(cv["height_m"] * length_factor, _MAX_SHADOW_M)
                # Shadow centre: caster displaced down-sun by shadow_len. Azimuth
                # is degrees clockwise from north → north component = cos, east
                # component = sin.
                dlat = (shadow_len * math.cos(shadow_dir)) / 111320.0
                dlng = (shadow_len * math.sin(shadow_dir)) / (111320.0 * cos_lat)
                s_lat = cv["lat"] + dlat
                s_lng = cv["lng"] + dlng
                # Any cell within the caster's canopy radius of the shadow centre
                # is in shade for this moment.
                rad_lat = cv["radius_m"] / 111320.0
                rad_lng = cv["radius_m"] / (111320.0 * cos_lat)
                for r in range(rows):
                    for c in range(cols):
                        clat, clng = _cell_ll(r, c)
                        ndx = (clng - s_lng) / rad_lng if rad_lng else 0.0
                        ndy = (clat - s_lat) / rad_lat if rad_lat else 0.0
                        if ndx * ndx + ndy * ndy <= 1.0:
                            out[r][c] += 1.0

    if samples:
        for r in range(rows):
            for c in range(cols):
                out[r][c] = min(1.0, out[r][c] / samples)
    return out


def shade_grid_for_design(project_dict: dict, elev: dict,
                          extra_casters: Optional[list] = None
                          ) -> list[list[float]]:
    """Convenience wrapper: gather casters from the project (existing + placed)
    plus any ``extra_casters`` (e.g. trees about to be placed) and compute the
    shade fraction grid over ``elev``."""
    casters = casters_from_project(project_dict)
    if extra_casters:
        casters = casters + list(extra_casters)
    return shade_grid(casters, elev)
