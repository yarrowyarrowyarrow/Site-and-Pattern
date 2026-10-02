"""
src/landing_check.py — where a placement landed, in words (F198, V3.05).

Design principle P9 — see docs/DESIGN_PHILOSOPHY.md: inform, never refuse.

The V2.98 review placed a row of four shrubs that came down half outside the
yard's boundary, on top of grasses and wildflowers, and nothing said so. V2.99's
footprint shows a placement's size *before* the click; this says what happened
*after* it: how many of the plants just placed are outside every drawn boundary,
and which sit inside another plant's circle.

It informs and never refuses. Overlap is often the design (a groundcover under
a shrub, bulbs through a mat), and a boundary drawn loosely is still the yard,
so the note says what is so and offers Undo; whether that is a problem is the
designer's to decide. A circle here is the one the map draws for a plant, half
its spacing (``html/map/03-plants.js``), so "inside its circle" means what the
person can see.

Qt-free; ``src/placement_bar_flow.py`` runs it after each placement.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable, NamedTuple, Optional

#: The map's floor on a marker's radius, in metres (03-plants.js).
MIN_RADIUS_M = 0.05


class Landing(NamedTuple):
    placed: int                   # plants in this placement
    outside: int                  # of them, outside every boundary drawn
    on_top: list                  # [(new name, existing name)], each new once
    has_boundary: bool


def _metres(a_lat, a_lng, b_lat, b_lng) -> float:
    """Planar distance in metres by the cos-lat metric src/projection.py uses
    at yard scale."""
    k = 111320.0
    dx = (b_lng - a_lng) * k * math.cos(math.radians((a_lat + b_lat) / 2.0))
    dy = (b_lat - a_lat) * k
    return math.hypot(dx, dy)


def _inside(lat: float, lng: float, ring: list) -> bool:
    """Ray-casting point-in-polygon on a ``[[lat, lng], ...]`` ring."""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i][0], ring[i][1]
        yj, xj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat):
            x_cross = xi + (lat - yi) * (xj - xi) / ((yj - yi) or 1e-15)
            if lng < x_cross:
                inside = not inside
        j = i
    return inside


def boundary_rings(project: dict) -> list:
    """Every property boundary as a ``[[lat, lng], ...]`` ring."""
    rings = []
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        geom = f.get("geometry", {}) or {}
        if (props.get("element_type") == "property_boundary"
                and geom.get("type") == "Polygon" and geom.get("coordinates")):
            rings.append([[pt[1], pt[0]] for pt in geom["coordinates"][0]])
    return rings


def check(new: Iterable[dict], existing: Iterable[dict], rings: list,
          radius_m: Callable[[object], float]) -> Landing:
    """Where the plants in ``new`` landed, against the plants already placed
    (``existing``) and the boundary ``rings``. Each plant is a placed-plant
    record (``plant_id``, ``common_name``, ``lat``, ``lng``); ``radius_m``
    gives a plant id's circle on the map."""
    new = [p for p in new if p.get("lat") is not None]
    existing = [p for p in existing if p.get("lat") is not None]
    outside = 0
    if rings:
        outside = sum(1 for p in new
                      if not any(_inside(p["lat"], p["lng"], r) for r in rings))
    on_top = []
    radii: dict = {}

    def r(pid):
        if pid not in radii:
            try:
                radii[pid] = max(float(radius_m(pid)), MIN_RADIUS_M)
            except (TypeError, ValueError):
                radii[pid] = MIN_RADIUS_M
        return radii[pid]

    for p in new:
        for q in existing:
            d = _metres(p["lat"], p["lng"], q["lat"], q["lng"])
            # One centre inside the other's drawn circle.
            if d < max(r(p.get("plant_id")), r(q.get("plant_id"))):
                on_top.append((p.get("common_name") or "a plant",
                               q.get("common_name") or "a plant"))
                break
    return Landing(len(new), outside, on_top, bool(rings))


def note(landing: Optional[Landing]) -> str:
    """One plain sentence for the placement bar, or ``""`` when nothing
    landed anywhere worth mentioning."""
    if landing is None or not landing.placed:
        return ""
    parts = []
    n = landing.placed
    if landing.outside:
        parts.append(f"all {n} landed outside the boundary"
                     if landing.outside == n and n > 1
                     else ("it landed outside the boundary" if n == 1
                           else f"{landing.outside} of {n} landed outside "
                                "the boundary"))
    if landing.on_top:
        k = len(landing.on_top)
        first = landing.on_top[0][1]
        if n == 1:
            parts.append(f"it sits inside {first}'s circle")
        elif k == 1:
            parts.append(f"1 sits inside {first}'s circle")
        else:
            others = len({b for _, b in landing.on_top}) - 1
            parts.append(f"{k} sit inside other plants' circles ({first}"
                         + (f" and {others} more)" if others else ")"))
    if not parts:
        return ""
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + "."
