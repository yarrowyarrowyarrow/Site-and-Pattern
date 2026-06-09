"""
src/area_fill.py — fill a drawn polygon with plants (N3′).

Generalises the old "seed-mix broadcast zone" idea: given a drawn polygon (a
GeoJSON ``[lng, lat]`` ring), lay out interior placement points on a spacing grid
and assign each to a species — a single species, or for a community/mix
distributed across the members by relative cover weight. Pure, Qt-free, DB-free;
reuses ``src.geometry``'s point-in-polygon. A controller turns the resulting
``(key, lat, lng)`` records into placed plants with the same machinery the design
generator uses, so the rendering/undo/scoring all come for free.
"""

from __future__ import annotations

import math

from src.geometry import point_in_ring, ring_bbox

_M_PER_DEG_LAT = 111_320.0


def _deg_steps(spacing_m: float, lat0: float) -> tuple[float, float]:
    """(d_lat, d_lng) in degrees for a ``spacing_m`` grid at latitude ``lat0``
    (ad-hoc cosLat projection, matching the rest of the app)."""
    d_lat = spacing_m / _M_PER_DEG_LAT
    d_lng = spacing_m / (_M_PER_DEG_LAT * max(0.05, math.cos(math.radians(lat0))))
    return d_lat, d_lng


def fill_points(ring, spacing_m: float, jitter: float = 0.0, rng=None) -> list:
    """Interior points ``(lat, lng)`` on a hex-offset grid stepped by
    ``spacing_m`` metres. ``ring`` is a list of ``[lng, lat]`` pairs. ``jitter``
    (0..1) adds up to that fraction of a cell of random offset — only applied
    when an ``rng`` is supplied, so the default output is deterministic."""
    if not ring or spacing_m <= 0:
        return []
    min_lat, min_lng, max_lat, max_lng = ring_bbox(ring)
    lat0 = (min_lat + max_lat) / 2.0
    d_lat, d_lng = _deg_steps(spacing_m, lat0)
    if d_lat <= 0 or d_lng <= 0:
        return []
    jit = max(0.0, min(1.0, jitter))
    pts: list[tuple[float, float]] = []
    row = 0
    lat = min_lat + d_lat / 2.0
    while lat <= max_lat:
        # offset alternate rows by half a cell → a more natural, less gridded look
        off = (d_lng / 2.0) if (row % 2) else 0.0
        lng = min_lng + d_lng / 2.0 + off
        while lng <= max_lng:
            plat, plng = lat, lng
            if jit and rng is not None:
                plat += (rng.random() - 0.5) * jit * d_lat
                plng += (rng.random() - 0.5) * jit * d_lng
            # Round first, then test, so every returned point is genuinely
            # inside at the stored precision (no near-edge point slips across).
            plat, plng = round(plat, 7), round(plng, 7)
            if point_in_ring(plat, plng, ring):
                pts.append((plat, plng))
            lng += d_lng
        lat += d_lat
        row += 1
    return pts


def assign_members(points, members) -> list:
    """Distribute ``points`` across ``members`` by weight (cover %).

    ``members`` is a list of ``(key, weight)`` — weights need not sum to 1; a
    non-positive total falls back to an even split. Uses largest-remainder
    allocation so counts stay proportional and sum exactly to ``len(points)``,
    then round-robins the keys across points so species are spatially intermixed
    rather than placed in blocks. Returns ``[(key, lat, lng), ...]``."""
    pts = list(points)
    n = len(pts)
    if n == 0 or not members:
        return []
    keys = [m[0] for m in members]
    weights = [max(0.0, float(m[1])) for m in members]
    total = sum(weights)
    if total <= 0:
        weights = [1.0] * len(members)
        total = float(len(members))

    raw = [w / total * n for w in weights]
    counts = [int(math.floor(r)) for r in raw]
    remainder = n - sum(counts)
    order = sorted(range(len(members)),
                   key=lambda i: raw[i] - counts[i], reverse=True)
    for k in range(remainder):
        counts[order[k % len(order)]] += 1

    pools = [[keys[i]] * counts[i] for i in range(len(members))]
    seq: list = []
    while any(pools):
        for pool in pools:
            if pool:
                seq.append(pool.pop())
    return [(seq[i], pts[i][0], pts[i][1]) for i in range(n)]


def plan_fill(ring, members, spacing_m: float, jitter: float = 0.0, rng=None) -> list:
    """End-to-end: lay out the grid in ``ring`` and assign species. Returns
    ``[(key, lat, lng), ...]``. ``members`` may be a single ``(key, weight)``
    list or, for a single species, ``[(plant_id, 1)]``."""
    return assign_members(fill_points(ring, spacing_m, jitter, rng), members)
