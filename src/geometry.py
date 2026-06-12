"""
geometry.py — Shared 2-D geometry helpers (Qt-free, no external deps).

Extracted from ``src/ecoregion.py`` in V1.48 so the same ray-casting
point-in-polygon test can back both ecoregion lookup AND the design
generator's boundary clipping (``src/llm_design.py``). Keeping it in one
place avoids two divergent copies of a subtle algorithm.

All rings/polygons follow the **GeoJSON convention**: a ring is a list of
``[lng, lat]`` pairs; a polygon is ``[exterior_ring, *hole_rings]``. The
public functions take ``(lat, lng)`` as separate scalars (the order the
rest of the app passes coordinates) and handle the lng/lat swap internally.

Pure Python, lat/lng comparison with no projection — correct for the
point-in-polygon decision regardless of projection (a point is inside the
same ring whether or not the plane is distorted).
"""

from __future__ import annotations


def point_in_ring(lat: float, lng: float, ring: list[list[float]]) -> bool:
    """Standard ray-casting point-in-polygon test. ``ring`` is a list of
    [lng, lat] pairs (GeoJSON convention) describing a closed ring.

    Casts a horizontal ray east from (lng, lat) and counts the number
    of times it crosses polygon edges; odd = inside, even = outside.
    Robust against ring vertex ordering (CW or CCW both work)."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # Edge from (xj, yj) to (xi, yi) straddles the horizontal line
        # at y=lat, and the intersection x is east of lng.
        intersect = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_in_polygon(lat: float, lng: float,
                     polygon: list[list[list[float]]]) -> bool:
    """GeoJSON Polygon = exterior ring + zero or more holes. Inside =
    point in the exterior ring AND not in any hole."""
    if not polygon:
        return False
    exterior = polygon[0]
    if not point_in_ring(lat, lng, exterior):
        return False
    for hole in polygon[1:]:
        if point_in_ring(lat, lng, hole):
            return False
    return True


def ring_bbox(ring: list[list[float]]) -> tuple[float, float, float, float]:
    """Bounding box of a [lng, lat] ring as ``(min_lat, min_lng, max_lat,
    max_lng)``. Raises ValueError on an empty ring."""
    if not ring:
        raise ValueError("empty ring")
    lngs = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (min(lats), min(lngs), max(lats), max(lngs))
