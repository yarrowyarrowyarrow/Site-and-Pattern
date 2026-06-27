"""
zoning.py — Derive wet / dry / shaded micro-zones for a property (V1.48).

The design generator uses these zones to place the right plant in the right
spot: moisture-loving and aquatic plants in the low/wet pockets, drought-
tolerant plants on the dry high slopes, shade-tolerant plants where the terrain
(and cast shade — see ``src/shade.py``) keeps the ground cool.

Everything here is **Qt-free** and **degrades gracefully**: if no elevation
grid can be obtained (offline, no boundary, network down) the public entry
points return ``None`` / empty and the caller falls back to property-wide fit.

Reuses ``src/terrain.py`` for the elevation grid + slope, and the row-major
grid geometry (row 0 = north edge) so cell→(lat,lng) matches the rest of the
app. Wetness is a *relative* terrain signal (low ground + local depressions),
not a hydrology model — enough to steer placement, honest about its limits.
"""

from __future__ import annotations

import math
from typing import Optional

from src.plant_conditions import condition_tokens

# Zone labels (module-level constants so callers compare symbolically).
WET = "wet"
DRY = "dry"
SHADED = "shaded"
NEUTRAL = "neutral"

# Tuning. A cell is DRY when its slope exceeds this and it sits in the upper
# half of the elevation range; WET when it is in the lowest quartile or a local
# depression. These thresholds favour *clear* signals — ambiguous cells stay
# NEUTRAL rather than being mislabelled.
_DRY_SLOPE_PCT = 12.0
_WET_QUANTILE = 0.25
_DEFAULT_RADIUS_M = 30.0          # half-extent of the bbox around a bare pin
_MIN_GRID_RES_M = 10.0            # matches terrain._MIN_RESOLUTION_M intent


def _boundary_bbox(boundary) -> Optional[dict]:
    """North/south/east/west bbox dict (terrain.py convention) from a boundary
    given as ``(lat, lng)`` tuples. ``None`` for a degenerate boundary."""
    if not boundary or len(boundary) < 3:
        return None
    lats = [float(p[0]) for p in boundary]
    lngs = [float(p[1]) for p in boundary]
    return {"north": max(lats), "south": min(lats),
            "east": max(lngs), "west": min(lngs)}


def _pin_bbox(site_config, radius_m: float = _DEFAULT_RADIUS_M
              ) -> Optional[dict]:
    """A square bbox of half-extent ``radius_m`` around the property pin."""
    sc = site_config or {}
    lat, lng = sc.get("latitude"), sc.get("longitude")
    if lat is None or lng is None:
        return None
    lat = float(lat); lng = float(lng)
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    dlat = radius_m / 111320.0
    dlng = radius_m / (111320.0 * cos_lat)
    return {"north": lat + dlat, "south": lat - dlat,
            "east": lng + dlng, "west": lng - dlng}


def site_elevation_grid(boundary, site_config,
                        resolution_m: float = _MIN_GRID_RES_M) -> Optional[dict]:
    """Fetch (cache-first) an elevation grid covering the boundary, or a default
    radius around the pin. Returns the ``terrain`` grid dict
    ``{grid, cols, rows, bbox}`` or ``None`` on any failure — callers then fall
    back to property-wide placement."""
    bbox = _boundary_bbox(boundary) or _pin_bbox(site_config)
    if bbox is None:
        return None
    try:
        from src import terrain
        if terrain.validate_bbox(bbox, resolution_m):   # returns an error string
            # Too small/dense/large — try a coarser sample once, else give up.
            resolution_m = max(resolution_m, _MIN_GRID_RES_M * 2)
            if terrain.validate_bbox(bbox, resolution_m):
                return None
        return terrain.fetch_openmeteo_grid(bbox, resolution_m)
    except Exception:  # noqa: BLE001 — zoning is best-effort
        return None


def cell_latlng(elev: dict, r: int, c: int) -> tuple[float, float]:
    """(lat, lng) of grid cell (r, c). Row 0 = north edge — same geometry as
    ``terrain._grid_points``."""
    bbox = elev["bbox"]
    rows = elev.get("rows", len(elev["grid"]))
    cols = elev.get("cols", len(elev["grid"][0]) if elev["grid"] else 0)
    t = r / max(1, rows - 1)
    u = c / max(1, cols - 1)
    lat = bbox["north"] - t * (bbox["north"] - bbox["south"])
    lng = bbox["west"] + u * (bbox["east"] - bbox["west"])
    return (lat, lng)


def _is_depression(grid, r, c, rows, cols) -> bool:
    """True when a cell is lower than every existing neighbour (a local sink)."""
    here = grid[r][c]
    lower_than_all = True
    saw_neighbour = False
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            rr, cc = r + dr, c + dc
            if 0 <= rr < rows and 0 <= cc < cols:
                saw_neighbour = True
                if grid[rr][cc] <= here:
                    lower_than_all = False
    return saw_neighbour and lower_than_all


def classify_zones(elev: Optional[dict],
                   shade_grid: Optional[list] = None) -> dict:
    """Classify each grid cell into WET / DRY / SHADED / NEUTRAL.

    Returns ``{(r, c): zone}``. ``shade_grid`` (optional, from
    ``src.shade.shade_grid``) is a parallel ``[[fraction]]``; cells shaded a
    meaningful fraction of the day become SHADED (this takes priority since a
    cool shaded hollow should grow shade plants, not be called merely "wet").
    Empty dict when there is no grid."""
    if not elev or not elev.get("grid"):
        return {}
    grid = elev["grid"]
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)

    flat = [v for row in grid for v in row]
    if not flat:
        return {}
    lo, hi = min(flat), max(flat)
    span = (hi - lo) or 1e-9
    srt = sorted(flat)
    wet_cut = srt[max(0, int(_WET_QUANTILE * (len(srt) - 1)))]

    try:
        from src import terrain
        slope = terrain.compute_slope_grid(elev)
    except Exception:  # noqa: BLE001
        slope = [[0.0] * cols for _ in range(rows)]

    shade_thresh = 0.4
    zones: dict = {}
    for r in range(rows):
        for c in range(cols):
            if (shade_grid is not None and r < len(shade_grid)
                    and c < len(shade_grid[r])
                    and shade_grid[r][c] >= shade_thresh):
                zones[(r, c)] = SHADED
                continue
            elev_frac = (grid[r][c] - lo) / span
            if grid[r][c] <= wet_cut or _is_depression(grid, r, c, rows, cols):
                zones[(r, c)] = WET
            elif slope[r][c] >= _DRY_SLOPE_PCT and elev_frac >= 0.5:
                zones[(r, c)] = DRY
            else:
                zones[(r, c)] = NEUTRAL
    return zones


def zone_positions(elev: Optional[dict], zones: dict, boundary=None
                   ) -> dict:
    """Group in-boundary cell centres by zone:
    ``{zone: [(lat, lng), ...]}``. When a boundary is supplied, only cells that
    fall inside it are kept (so zoned placement is also clipped)."""
    out: dict = {WET: [], DRY: [], SHADED: [], NEUTRAL: []}
    if not elev or not zones:
        return out
    poly = None
    if boundary and len(boundary) >= 3:
        ring = [[float(p[1]), float(p[0])] for p in boundary]  # (lat,lng)→[lng,lat]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        poly = [ring]
    from src.geometry import point_in_polygon
    for (r, c), z in zones.items():
        lat, lng = cell_latlng(elev, r, c)
        if poly is not None and not point_in_polygon(lat, lng, poly):
            continue
        out.setdefault(z, []).append((lat, lng))
    return out


def preferred_zone_for_plant(plant: dict) -> str:
    """Map a plant row to the zone it most wants, using existing columns only:
    aquatic / riparian / high-water → WET; full-shade or partial-shade →
    SHADED; low-water → DRY; otherwise NEUTRAL. (WET and SHADED both apply to
    e.g. a shade-loving bog plant — WET wins, since moisture is the harder
    constraint.)"""
    ptype = (plant.get("plant_type") or "").lower()
    eco = (plant.get("ab_ecoregion") or "").lower()
    # water_needs / sun_requirement may list several tolerances (V1.84); treat
    # each as a set and match on membership.
    water = set(condition_tokens(plant.get("water_needs")))
    sun = set(condition_tokens(plant.get("sun_requirement")))
    if (ptype == "aquatic" or "high" in water
            or "wet_meadow" in eco or "riparian" in eco):
        return WET
    if sun & {"full_shade", "partial_shade"}:
        return SHADED
    if "low" in water:
        return DRY
    return NEUTRAL


# Structures that belong in low / wet ground (the water-management group).
WET_STRUCTURE_IDS = frozenset({"pond", "swale", "rain_garden", "rain_barrel"})


def preferred_zone_for_structure(struct_id: str) -> str:
    """Water structures want WET/low ground; everything else is NEUTRAL (the
    generator may still nudge sun-loving structures toward open cells)."""
    return WET if struct_id in WET_STRUCTURE_IDS else NEUTRAL
