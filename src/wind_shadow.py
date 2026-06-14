"""
wind_shadow.py — porosity-aware shelterbelt (wind shadow) geometry (V1.68).

The leeward "wind shadow" of placed plants, as merged, banded polygons for the
live map overlay. Pure + Qt-free; reuses the metric projection and lat/lng
projection-back helpers from ``src/shadow_geometry.py`` and shapely for the
union, so it's unit-testable headlessly.

Model (schematic but honest about shelterbelt physics):
  * Shelter projects **downwind** — toward ``wind_from_deg + 180``.
  * Effective reach scales with **porosity**: a ~50%-porous barrier shelters
    farthest (~15× height); a solid barrier (turbulent) or a very open one both
    reach less (~8× H). A lone dense tree is a poor windbreak — hence callers
    merge per-plant shadows into one footprint.
  * Three distance **bands** (strong / moderate / weak) encode the calm→exposed
    gradient as discrete polygons (reliable on Leaflet; true gradients aren't).

Public API: :func:`porosity_for`, :func:`reach_h_factor`, :func:`merged_shelter`,
:func:`casters_from_project`.
"""

from __future__ import annotations

import math
from typing import Optional

from src.shadow_geometry import _HAVE_SHAPELY, _MetricOrigin, latlng_rings

if _HAVE_SHAPELY:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

# Distance bands as fractions of total reach, outer→inner (draw order: weak
# first, strong on top). Strengths drive the overlay opacity.
_BANDS = [(0.70, 1.00, "weak"), (0.40, 0.70, "moderate"), (0.0, 0.40, "strong")]
_MAX_REACH_M = 250.0          # clamp so a tall caster can't blanket the map
_PEAK_POROSITY = 0.5


def reach_h_factor(porosity: float) -> float:
    """Shelter reach in multiples of height for a given porosity (0..1).
    Peaks at ~15×H near 50% porosity; ~8×H for solid (0) or very open (1)."""
    p = max(0.0, min(1.0, porosity))
    return 15.0 - 14.0 * abs(p - _PEAK_POROSITY)


def porosity_for(plant: dict) -> float:
    """Best porosity estimate for a plant: an explicit trait if present, else a
    per-type default (denser conifers/evergreens shelter less far)."""
    for key in ("wind_porosity", "porosity"):
        v = (plant or {}).get(key)
        if isinstance(v, (int, float)) and 0.0 < float(v) <= 1.0:
            return float(v)
    notes = ((plant or {}).get("notes") or "").lower()
    if (plant or {}).get("evergreen") or "conifer" in notes or "spruce" in notes \
            or "pine" in notes:
        return 0.3
    return 0.5            # deciduous tree/shrub ≈ optimal


def _band_polygon(cx, cy, wind_from_deg, r0, r1, w0, w1):
    """Trapezoid from distance r0→r1 downwind of (cx, cy), width w0→w1."""
    thd = math.radians((wind_from_deg + 180.0) % 360.0)
    ux, uy = math.sin(thd), math.cos(thd)        # downwind unit (x east, y north)
    px, py = math.cos(thd), -math.sin(thd)       # perpendicular unit
    n0x, n0y = cx + ux * r0, cy + uy * r0
    n1x, n1y = cx + ux * r1, cy + uy * r1
    return Polygon([(n0x + px * w0, n0y + py * w0),
                    (n0x - px * w0, n0y - py * w0),
                    (n1x - px * w1, n1y - py * w1),
                    (n1x + px * w1, n1y + py * w1)])


def merged_shelter(casters: list, wind_from_deg: float,
                   origin: Optional["_MetricOrigin"] = None) -> dict:
    """Per-plant porosity-aware shelter, **merged** per strength band.

    ``casters`` are dicts ``{lat, lng, height_m, half_width_m, porosity}``.
    Returns ``{"bands": [{"strength", "rings": [[[lat,lng]…]…]}, …],
    "wind_from_deg": ..}`` — bands ordered weak→strong (draw order), each a
    union of every caster's band polygon, as nested lat/lng rings for
    ``L.polygon``. Empty when shapely is absent or there are no casters."""
    if not _HAVE_SHAPELY or not casters:
        return {"bands": [], "wind_from_deg": wind_from_deg}
    if origin is None:
        alat = sum(c["lat"] for c in casters) / len(casters)
        alng = sum(c["lng"] for c in casters) / len(casters)
        origin = _MetricOrigin(alat, alng)

    by_band: dict[str, list] = {}
    for c in casters:
        cx, cy = origin.to_xy(c["lng"], c["lat"])
        reach = min(_MAX_REACH_M,
                    reach_h_factor(c["porosity"]) * float(c["height_m"]))
        hw = max(0.3, float(c["half_width_m"]))
        for f0, f1, strength in _BANDS:
            r0, r1 = f0 * reach, f1 * reach
            if r1 - r0 < 0.1:
                continue
            w0 = hw * (1.0 - 0.6 * f0)
            w1 = hw * max(0.4, 1.0 - 0.6 * f1)
            poly = _band_polygon(cx, cy, wind_from_deg, r0, r1, w0, w1)
            if poly.is_valid and not poly.is_empty:
                by_band.setdefault(strength, []).append(poly)

    bands = []
    for _f0, _f1, strength in _BANDS:        # weak → strong (draw order)
        polys = by_band.get(strength)
        if not polys:
            continue
        u = unary_union(polys)
        if not u.is_valid:
            u = u.buffer(0)
        rings = latlng_rings(u, origin)
        if rings:
            bands.append({"strength": strength, "rings": rings})
    return {"bands": bands, "wind_from_deg": float(wind_from_deg)}


def casters_from_project(project: dict, year: int = 0,
                         get_plant=None) -> list:
    """Build wind-shadow casters from a project's placed trees/shrubs, with
    heights scaled to the growth-timeline ``year`` (reuses ``scene3d``). Short
    plants (<1 m) are skipped — they don't shelter. ``get_plant`` injectable."""
    from src.project_store import plant_record_from_feature
    from src.scene3d import plant_3d_state
    if get_plant is None:
        from src.db.plants import get_plant as _gp
        get_plant = _gp
    cache: dict = {}
    casters: list = []
    for f in project.get("features", []):
        rec = plant_record_from_feature(f)
        if rec is None:
            continue
        pid = rec["plant_id"]
        plant = cache.get(pid)
        if plant is None:
            plant = get_plant(pid) or {}
            cache[pid] = plant
        if (plant.get("plant_type") or "") not in ("tree", "shrub"):
            continue
        st = plant_3d_state(plant, rec["lat"], rec["lng"], year)
        h = float(st.get("height_m") or 0.0)
        if h < 1.0:
            continue
        casters.append({
            "id": pid,
            "lat": rec["lat"], "lng": rec["lng"],
            "height_m": h,
            "half_width_m": max(0.3, float(st.get("canopy_m") or 1.0) / 2.0),
            "porosity": porosity_for(plant),
        })
    return casters
