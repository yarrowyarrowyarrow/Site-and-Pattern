"""
exclusion.py — Keep-out zones for the design generator (V1.50).

Stops generated plants from landing on top of things that are already there:
user-marked / auto-imported existing trees and buildings, and the design's own
water structures (a pond/swale/rain garden shouldn't sprout plants in its
middle). Each keep-out is modelled as a circle ``(lat, lng, radius_m)``; a
candidate position is rejected when it falls inside any circle.

Qt-free, no deps. Distance uses the same local cos-lat metric projection as
``src/layout.py`` / ``src/llm_design.py`` so it agrees with placement and
clipping (≈1 % error under ~2 km, well within planting tolerance).

Feature sources (project FeatureCollection):
  * ``existing_tree``     → canopy_radius_m (fallback size_m/2).
  * ``existing_building`` → canopy_radius_m (footprint half-width).
  * ``canopy_footprint`` imported from OSM (``source="osm"``) → stored centroid
    + canopy_radius_m (V1.58: OSM buildings are polygons, not points, but still
    keep planting out).
  * ``structure`` whose struct id is a water feature → struct size_m / 2.
"""

from __future__ import annotations

import math

_M_PER_DEG = 111320.0

# Design-placed structures that should exclude planting on top (the water-
# management group; mirrors zoning.WET_STRUCTURE_IDS but kept local so exclusion
# has no import cycle and can diverge if needed).
EXCLUDING_STRUCTURE_IDS = frozenset({"pond", "swale", "rain_garden", "rain_barrel"})


def _struct_id_of(props: dict) -> str:
    """A structure feature stores its id either directly (``struct_id``, the
    interactive path) or inside ``struct_def`` (the generator path)."""
    return (props.get("struct_id")
            or (props.get("struct_def") or {}).get("id")
            or "")


def keepout_circles(project_dict: dict) -> list[tuple[float, float, float]]:
    """Collect keep-out circles ``(lat, lng, radius_m)`` from a project. Empty
    list when there's nothing to avoid."""
    circles: list[tuple[float, float, float]] = []
    for f in (project_dict or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        et = props.get("element_type")
        geom = f.get("geometry", {}) or {}
        if geom.get("type") != "Point":
            # V1.58: OSM buildings import as canopy_footprint Polygons but must
            # still keep planting out. They stamp a centroid + canopy_radius_m at
            # import, so reuse those rather than re-deriving the ring here. Any
            # other non-point geometry is skipped defensively.
            if et == "canopy_footprint" and props.get("source") == "osm":
                la, ln = props.get("lat"), props.get("lng")
                r = props.get("canopy_radius_m")
                if la is not None and ln is not None and r:
                    circles.append((float(la), float(ln), max(0.5, float(r))))
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]

        if et in ("existing_tree", "existing_building"):
            r = props.get("canopy_radius_m")
            if not r:
                r = float(props.get("size_m", 6.0)) / 2.0
            circles.append((lat, lng, max(0.5, float(r))))
        elif et == "structure":
            sid = _struct_id_of(props)
            if sid in EXCLUDING_STRUCTURE_IDS:
                size = props.get("size_m") or (
                    props.get("struct_def") or {}).get("size_m") or 4.0
                circles.append((lat, lng, max(0.5, float(size) / 2.0)))
    return circles


def is_clear(lat: float, lng: float,
             circles: list[tuple[float, float, float]],
             extra_margin_m: float = 0.0) -> bool:
    """True when ``(lat, lng)`` is outside every keep-out circle (optionally
    enlarged by ``extra_margin_m``, e.g. half a plant's canopy so the plant
    body — not just its centre — clears the obstacle)."""
    if not circles:
        return True
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    for clat, clng, radius in circles:
        dx = (lng - clng) * _M_PER_DEG * cos_lat
        dy = (lat - clat) * _M_PER_DEG
        if dx * dx + dy * dy < (radius + extra_margin_m) ** 2:
            return False
    return True


def filter_clear(positions, circles, extra_margin_m: float = 0.0):
    """Keep only the positions that clear every keep-out circle. Accepts and
    returns ``(lat, lng)`` tuples."""
    if not circles:
        return list(positions)
    return [p for p in positions
            if is_clear(p[0], p[1], circles, extra_margin_m)]
