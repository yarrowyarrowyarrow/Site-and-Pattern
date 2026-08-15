"""
src/frontage.py — which edge faces the street (V2.58).

Design principle P9 (uncertainty is a feature — ship ranges and confidence,
never false precision) — see docs/DESIGN_PHILOSOPHY.md.

:mod:`src.cues_to_care` needs to know which side of a property the public sees,
because "a mown strip along the frontage" is the strongest cue there is. Until
now it could not: nothing in this app knew where the road was, so it reused the
assumption the ``sidewalk`` camera already documents — *the south edge, "because
that is the street side of a north-facing prairie lot far more often than not"*
— and said so in the line it affected.

    Author's request (V2.58): *"lets find a way to add the road data."*

So this measures it. :func:`src.osm_features.fetch_roads` pulls street
centrelines from the same Overpass source that already supplies trees and
buildings; this module turns those plus a property boundary into *which edge*.

**The assumption does not go away, it gets demoted.** There is no road data for
every property, no network on every run, and no guarantee OSM has the street.
So the result always says which of the two it is — measured or assumed — and the
caller prints that word. A measurement that cannot say when it is a guess is
worse than a guess that admits it.

Qt-free and network-free: roads come in as data, so every case here is testable
without touching Overpass.
"""

from __future__ import annotations

import math
from typing import NamedTuple, Optional

#: A road further than this from the boundary is not this property's frontage —
#: it is the next street over. Generous enough for a deep rural lot, tight
#: enough that a parallel back lane does not win over the actual street.
MAX_ROAD_DISTANCE_M = 60.0

#: Compass names for the eight sectors, used when reporting which edge it is.
_COMPASS = ("north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west")


class Frontage(NamedTuple):
    """Which way the property faces, and how confidently.

    ``bearing`` is degrees clockwise from north, pointing *from* the property
    centre *toward* the street. ``measured`` is False when this is the
    south-edge fallback rather than a road observation.
    """
    bearing: float
    side: str
    measured: bool
    road_name: str = ""
    distance_m: Optional[float] = None

    @property
    def note(self) -> str:
        """The phrase the caller puts in the sentence it affects."""
        if not self.measured:
            return ("assuming the street is on the south side, as the "
                    "sidewalk view does")
        where = f" ({self.road_name})" if self.road_name else ""
        return f"the {self.side} edge, from mapped road data{where}"


def compass(bearing: float) -> str:
    """The eight-point compass name for a bearing in degrees from north."""
    idx = int(((float(bearing) % 360.0) + 22.5) // 45.0) % 8
    return _COMPASS[idx]


#: What the app assumed before it could measure. Bearing 180 = due south.
ASSUMED = Frontage(bearing=180.0, side="south", measured=False)


def _centroid(ring: list) -> Optional[tuple]:
    """``(lat, lng)`` mean of a ``[[lng, lat], …]`` ring."""
    pts = [(p[1], p[0]) for p in ring or []
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts))


def _seg_nearest(pt: tuple, a: tuple, b: tuple) -> tuple:
    """``(distance_m, (lat, lng))`` of the closest point on segment ``a``–``b``.

    Returns the **projected** point, not the nearer endpoint. That distinction
    is not academic: a residential street runs well past the lot it serves, so
    both its endpoints can sit diagonally away from a property whose frontage is
    dead ahead. Taking the endpoint put a due-east street at "south-east" in
    testing — the frontage would have named the wrong edge on most real lots.

    Flat-earth in the local metric, via the app's shared projection, so this
    cannot drift from the geometry it is compared against.
    """
    from src.projection import metres_per_deg

    m_lat, m_lng = metres_per_deg(pt[0])
    ax, ay = (a[1] - pt[1]) * m_lng, (a[0] - pt[0]) * m_lat
    bx, by = (b[1] - pt[1]) * m_lng, (b[0] - pt[0]) * m_lat
    dx, dy = bx - ax, by - ay
    if dx == 0.0 and dy == 0.0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, (-ax * dx - ay * dy) / (dx * dx + dy * dy)))
    nx, ny = ax + t * dx, ay + t * dy
    # Back to lat/lng so the caller can take a bearing from it.
    return (math.hypot(nx, ny),
            (pt[0] + ny / (m_lat or 1.0), pt[1] + nx / (m_lng or 1.0)))


def _bearing_to(origin: tuple, target: tuple) -> float:
    """Degrees clockwise from north, ``origin`` → ``target``, both (lat, lng)."""
    from src.projection import metres_per_deg

    m_lat, m_lng = metres_per_deg(origin[0])
    east = (target[1] - origin[1]) * m_lng
    north = (target[0] - origin[0]) * m_lat
    return math.degrees(math.atan2(east, north)) % 360.0


def _nearest_point_on_road(centre: tuple, line: list) -> tuple:
    """``(distance_m, (lat, lng))`` of the closest point on a road line."""
    best_d, best_pt = float("inf"), None
    pts = [(p[1], p[0]) for p in line or []
           if isinstance(p, (list, tuple)) and len(p) >= 2]
    for a, b in zip(pts, pts[1:]):
        d, pt = _seg_nearest(centre, a, b)
        if d < best_d:
            best_d, best_pt = d, pt
    return (best_d, best_pt)


def frontage_from_roads(boundary_ring: list, roads: Optional[list],
                        *, max_distance_m: float = MAX_ROAD_DISTANCE_M
                        ) -> Frontage:
    """Which edge faces the street, measured where possible.

    ``boundary_ring`` is ``[[lng, lat], …]``; ``roads`` are
    :func:`src.osm_features.fetch_roads` dicts. Returns :data:`ASSUMED` when
    there is no boundary, no road data, or nothing close enough — never raises,
    and never silently upgrades a guess into a measurement.
    """
    centre = _centroid(boundary_ring)
    if centre is None or not roads:
        return ASSUMED

    best = None
    for road in roads:
        line = road.get("line") or []
        if len(line) < 2:
            continue
        dist, pt = _nearest_point_on_road(centre, line)
        if pt is None or dist > max_distance_m:
            continue
        if best is None or dist < best[0]:
            best = (dist, pt, road)
    if best is None:
        return ASSUMED

    dist, pt, road = best
    bearing = _bearing_to(centre, pt)
    return Frontage(bearing=bearing, side=compass(bearing), measured=True,
                    road_name=road.get("name") or "",
                    distance_m=round(dist, 1))


def frontage_for_project(project: dict, roads: Optional[list] = None
                         ) -> Frontage:
    """The project's frontage, from its stored roads unless some are passed in.

    Roads are read off the project so the answer survives offline: they are
    fetched once and kept with the design, exactly like the building footprints
    and the site's climate readings.
    """
    ring = _boundary_ring(project)
    if roads is None:
        roads = roads_in_project(project)
    return frontage_from_roads(ring, roads)


def _boundary_ring(project: dict) -> list:
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties") or {}
        if props.get("element_type") != "property_boundary":
            continue
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if coords and isinstance(coords[0], list):
            return coords[0] if isinstance(coords[0][0], list) else coords
    return []


#: Feature type the fetched roads are stored as on the project.
ROAD_ELEMENT_TYPE = "osm_road"


def roads_in_project(project: dict) -> list:
    out = []
    for f in (project or {}).get("features", []) or []:
        props = f.get("properties") or {}
        if props.get("element_type") != ROAD_ELEMENT_TYPE:
            continue
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) >= 2:
            out.append({"line": coords, "name": props.get("name") or "",
                        "highway": props.get("highway") or ""})
    return out


def store_roads(project: dict, roads: list) -> int:
    """Persist fetched roads on the project. Returns how many were stored.

    Replaces any previously stored set, so a re-fetch after the pin moves does
    not leave the old street behind.
    """
    feats = [f for f in (project or {}).get("features", []) or []
             if (f.get("properties") or {}).get("element_type")
             != ROAD_ELEMENT_TYPE]
    added = 0
    for road in roads or []:
        line = road.get("line") or []
        if len(line) < 2:
            continue
        feats.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": line},
            "properties": {"element_type": ROAD_ELEMENT_TYPE,
                           "name": road.get("name") or "",
                           "highway": road.get("highway") or ""},
        })
        added += 1
    project["features"] = feats
    return added
