"""
exclusion.py — Keep-out zones for the design generator (V1.50).

Stops generated plants from landing on top of things that are already there:
user-marked / auto-imported existing trees and buildings, and the design's own
water structures (a pond/swale/rain garden shouldn't sprout plants in its
middle). A point is kept out by a circle ``(lat, lng, radius_m)``; a candidate
position is rejected when it falls inside any circle.

**A drawn shape is kept out as the shape (V3.18, PY-3).** Until V3.18 a path, a
patio or a building footprint was kept out as one circle about its centre,
reaching its farthest corner, so a 1 x 10 m path blotted out a circle of 5 m
radius and half of a 15 x 10 m yard (42 plants fell to 18), and a patio over
the south 60% of a yard left room for 5. :func:`keepout_areas` keeps those as
polygons, tested in plain Python on a small local metric frame, and the
generator reads it; :func:`keepout_circles` remains the coarse view, every
keep-out as a circle.

Qt-free, no deps. Distance uses the same local cos-lat metric projection as
``src/layout.py`` / ``src/llm_design.py`` so it agrees with placement and
clipping (≈1 % error under ~2 km, well within planting tolerance).

Feature sources (project FeatureCollection):
  * ``existing_tree``     → canopy_radius_m (fallback size_m/2).
  * ``existing_building`` → canopy_radius_m (footprint half-width).
  * ``canopy_footprint`` Polygons (OSM buildings, hand-drawn building/canopy
    perimeters, nDSM-extracted footprints) → canopy_radius_m + a centroid
    (stored for OSM, else derived from the ring). They are polygons, not points,
    but still keep planting out.
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


# Drawn custom_shape shape_types the generator plants AROUND, not on, and the
# ones it plants INTO: one list with the overview's planting area since V3.28
# (PY-2, ``yard_overview.NOT_PLANTED`` and ``BED_SHAPES``), so a plan goes where
# the overview measures. Until then a Lawn Area was planted (32 of 42 plants on
# a lawn over 60% of a yard) and a Garden Bed was ignored (1 of 42 in it).
def _avoid_shape_types() -> set:
    from src.yard_overview import NOT_PLANTED
    return set(NOT_PLANTED)


def _fill_zone_shape_types() -> set:
    from src.yard_overview import BED_SHAPES
    return set(BED_SHAPES)


def fill_regions(project_dict: dict) -> list:
    """Rings ``[[lng, lat], …]`` of the drawn beds and conversion zones: the
    areas the generator plants INTO. Empty when none is drawn."""
    want = _fill_zone_shape_types()
    out: list = []
    for f in (project_dict or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        if (props.get("element_type") in ("custom_shape", "canopy_footprint")
                and props.get("shape_type") in want):
            ring = (f.get("geometry", {}) or {}).get("coordinates") or []
            if ring and ring[0] and len(ring[0]) >= 3:
                out.append(ring[0])
    return out


class _Shape:
    """A drawn keep-out polygon, in metres east and north of its first vertex.

    Built once a pass, so the per-candidate test is a bounding-box check and,
    near the shape, a ray cast and a distance to its edges: plain arithmetic on
    a handful of vertices, with no geometry library in the scoring loop."""

    __slots__ = ("lat0", "lng0", "kx", "pts", "box")

    def __init__(self, ring):
        self.lat0, self.lng0 = float(ring[0][1]), float(ring[0][0])
        self.kx = _M_PER_DEG * (math.cos(math.radians(self.lat0)) or 1e-9)
        pts = [((float(p[0]) - self.lng0) * self.kx,
                (float(p[1]) - self.lat0) * _M_PER_DEG) for p in ring]
        if pts[0] == pts[-1]:
            pts.pop()
        self.pts = pts
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.box = (min(xs), min(ys), max(xs), max(ys))

    def blocks(self, lat: float, lng: float, margin: float = 0.0) -> bool:
        """True when ``(lat, lng)`` is inside the shape or within ``margin``
        metres of its edge."""
        x = (lng - self.lng0) * self.kx
        y = (lat - self.lat0) * _M_PER_DEG
        x0, y0, x1, y1 = self.box
        if x < x0 - margin or x > x1 + margin or y < y0 - margin or y > y1 + margin:
            return False
        inside = False
        pts = self.pts
        j = len(pts) - 1
        for i in range(len(pts)):
            (xi, yi), (xj, yj) = pts[i], pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        if inside or margin <= 0:
            return inside
        m2 = margin * margin
        for i in range(len(pts)):
            (ax, ay), (bx, by) = pts[i - 1], pts[i]
            dx, dy = bx - ax, by - ay
            t = 0.0
            if dx or dy:
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy)
                                 / (dx * dx + dy * dy)))
            ex, ey = ax + t * dx - x, ay + t * dy - y
            if ex * ex + ey * ey < m2:
                return True
        return False


class KeepOut:
    """Everything a pass keeps planting out of: ``circles`` for points
    (existing trees, structures) and ``shapes`` for drawn areas and footprints.
    Adding two (or a list of circles) merges them; empty is falsy."""

    __slots__ = ("circles", "shapes")

    def __init__(self, circles=(), shapes=()):
        self.circles = list(circles)
        self.shapes = list(shapes)

    def __add__(self, other):
        o = as_keepout(other)
        return KeepOut(self.circles + o.circles, self.shapes + o.shapes)

    def __radd__(self, other):
        return as_keepout(other) + self

    def __bool__(self) -> bool:
        return bool(self.circles or self.shapes)

    def __repr__(self) -> str:
        return (f"KeepOut({len(self.circles)} circles, "
                f"{len(self.shapes)} shapes)")


def as_keepout(value) -> KeepOut:
    """A :class:`KeepOut` from one, from a list of circles, or from nothing."""
    if isinstance(value, KeepOut):
        return value
    return KeepOut(circles=list(value or []))


def _keepout_items(project_dict: dict):
    """Each keep-out in a project, as ``("circle", (lat, lng, r))`` or
    ``("shape", ring, (lat, lng, r))``, the circle being the coarse view of
    the shape."""
    from src.osm_features import ring_centroid, ring_radius_m   # ring helpers
    avoid_shapes = _avoid_shape_types()
    for f in (project_dict or {}).get("features", []) or []:
        props = f.get("properties", {}) or {}
        et = props.get("element_type")
        geom = f.get("geometry", {}) or {}
        # Drawn "existing remnant" / hardscape areas → keep planting out.
        if (et in ("custom_shape", "canopy_footprint")
                and props.get("shape_type") in avoid_shapes):
            ring = (geom.get("coordinates") or [None])[0]
            c = ring_centroid(ring) if ring else None
            if c is not None:
                yield ("shape", ring, (float(c[0]), float(c[1]),
                                       max(0.5, ring_radius_m(ring, c))))
            continue
        if geom.get("type") != "Point":
            # canopy_footprint Polygons (OSM buildings, hand-drawn building/canopy
            # perimeters, and nDSM-extracted footprints) carry a canopy_radius_m
            # and must keep planting out. OSM imports also stamp a centroid; for
            # the others derive it from the ring. Any other non-point geometry is
            # skipped defensively.
            if et == "canopy_footprint":
                r = props.get("canopy_radius_m")
                ring = (geom.get("coordinates") or [None])[0]
                la, ln = props.get("lat"), props.get("lng")
                if (la is None or ln is None):
                    c = ring_centroid(ring) if ring else None
                    if c is not None:
                        la, ln = c
                if la is not None and ln is not None and r:
                    circle = (float(la), float(ln), max(0.5, float(r)))
                    if ring and len(ring) >= 3:
                        yield ("shape", ring, circle)
                    else:
                        yield ("circle", circle)
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]

        if et in ("existing_tree", "existing_building"):
            r = props.get("canopy_radius_m")
            if not r:
                r = float(props.get("size_m", 6.0)) / 2.0
            yield ("circle", (lat, lng, max(0.5, float(r))))
        elif et == "structure":
            sid = _struct_id_of(props)
            if sid in EXCLUDING_STRUCTURE_IDS:
                size = props.get("size_m") or (
                    props.get("struct_def") or {}).get("size_m") or 4.0
                yield ("circle", (lat, lng, max(0.5, float(size) / 2.0)))


def keepout_areas(project_dict: dict) -> KeepOut:
    """What the generator keeps planting out of: points as circles, drawn
    areas and footprints as the polygons they are (V3.18)."""
    keep = KeepOut()
    for item in _keepout_items(project_dict):
        if item[0] == "shape":
            keep.shapes.append(_Shape(item[1]))
        else:
            keep.circles.append(item[1])
    return keep


def keepout_circles(project_dict: dict) -> list[tuple[float, float, float]]:
    """Every keep-out as a circle ``(lat, lng, radius_m)``, a drawn area as
    one about its centre reaching its farthest corner. The coarse view: the
    generator reads :func:`keepout_areas`. Empty when there's nothing."""
    return [item[-1] for item in _keepout_items(project_dict)]


def is_clear(lat: float, lng: float, circles,
             extra_margin_m: float = 0.0) -> bool:
    """True when ``(lat, lng)`` is outside every keep-out (optionally enlarged
    by ``extra_margin_m``, e.g. half a plant's canopy so the plant body — not
    just its centre — clears the obstacle). ``circles`` is a list of circles
    or a :class:`KeepOut`."""
    if not circles:
        return True
    keep = as_keepout(circles)
    cos_lat = math.cos(lat * math.pi / 180) or 1e-9
    for clat, clng, radius in keep.circles:
        dx = (lng - clng) * _M_PER_DEG * cos_lat
        dy = (lat - clat) * _M_PER_DEG
        if dx * dx + dy * dy < (radius + extra_margin_m) ** 2:
            return False
    for shape in keep.shapes:
        if shape.blocks(lat, lng, extra_margin_m):
            return False
    return True


def filter_clear(positions, circles, extra_margin_m: float = 0.0):
    """Keep only the positions that clear every keep-out circle. Accepts and
    returns ``(lat, lng)`` tuples."""
    if not circles:
        return list(positions)
    return [p for p in positions
            if is_clear(p[0], p[1], circles, extra_margin_m)]
