"""
shadow_geometry.py — Footprint-polygon shadow casting (V1.53).

The procedural core of the improved shade estimator. Where the legacy model in
``src/shade.py`` approximated every caster as a *circle* displaced down-sun, this
module casts the **true 2D footprint polygon** of a structure (a building
perimeter, a tree canopy, a placed plant's canopy) into a ground shadow:

  1. Project the footprint into a local metric plane (metres east / north of the
     site bbox SW corner) so the geometry is planar/Euclidean for shapely.
  2. Translate a copy of the footprint *down-sun* by ``height / tan(altitude)``.
  3. Take the convex hull of {footprint, translated footprint} — the silhouette
     the object sweeps as its shadow extends along the solar vector.
  4. Union every caster's shadow and rasterize onto the design's elevation grid,
     preserving the ``[[fraction]]`` grid contract the rest of the app consumes.

shapely is an **optional** dependency. Every entry point degrades gracefully:
``_HAVE_SHAPELY`` is False when shapely is absent, and ``src/shade.py`` falls
back to its built-in circle model so headless installs / CI keep working. This
mirrors the ``_HAVE_QT`` optional-import pattern already used in ``shade.py``.

Solar maths is reused verbatim from ``src/solar.py`` (no pvlib): azimuth is
degrees clockwise from north, altitude degrees above the horizon.
"""

from __future__ import annotations

import math
from typing import Optional

try:
    from shapely.geometry import Polygon, Point
    from shapely.ops import unary_union
    from shapely.prepared import prep
    from shapely import affinity
    _HAVE_SHAPELY = True
except ImportError:  # pragma: no cover - exercised on shapely-less installs
    _HAVE_SHAPELY = False

# Metres per degree of latitude (WGS-84 mean) — the same constant the legacy
# circle model and src/projection.py use, so metric geometry here lines up with
# the rest of the app's ad-hoc cosLat projection.
_M_PER_DEG_LAT = 111320.0

# Shared with src/shade.py — kept in sync so the polygon and circle paths agree
# on when the sun is too low to cast and how far a shadow may stretch.
_MIN_SUN_ALT = 5.0
_MAX_SHADOW_M = 60.0


# ── Local metric projection ───────────────────────────────────────────────────

class _MetricOrigin:
    """Forward/inverse transform between (lng, lat) and local metres about an
    anchor latitude/longitude (cosLat equirectangular, ~1% over a property).

    x grows east, y grows north — matching the azimuth decomposition used for
    the shadow vector (north = cos, east = sin)."""

    __slots__ = ("lat0", "lng0", "_cos_lat")

    def __init__(self, lat0: float, lng0: float):
        self.lat0 = lat0
        self.lng0 = lng0
        cos_lat = math.cos(math.radians(lat0))
        self._cos_lat = cos_lat if abs(cos_lat) > 1e-9 else 1e-9

    def to_xy(self, lng: float, lat: float) -> tuple[float, float]:
        x = (lng - self.lng0) * _M_PER_DEG_LAT * self._cos_lat
        y = (lat - self.lat0) * _M_PER_DEG_LAT
        return x, y


def origin_for_bbox(bbox: dict) -> "_MetricOrigin":
    """Build a metric origin anchored at a grid bbox's SW corner."""
    return _MetricOrigin(bbox["south"], bbox["west"])


# ── Footprint → metric polygon ────────────────────────────────────────────────

def footprint_to_metric(coords_lnglat, origin: "_MetricOrigin"):
    """Convert a GeoJSON ring of ``(lng, lat)`` pairs to a metric shapely
    ``Polygon``. Returns ``None`` if shapely is unavailable or the ring is
    degenerate (fewer than 3 distinct points)."""
    if not _HAVE_SHAPELY or not coords_lnglat:
        return None
    pts = [origin.to_xy(p[0], p[1]) for p in coords_lnglat]
    if len(pts) < 3:
        return None
    try:
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)          # repair self-touching rings
        return poly if (poly and not poly.is_empty) else None
    except Exception:  # noqa: BLE001
        return None


def point_footprint_metric(lng: float, lat: float, radius_m: float,
                           origin: "_MetricOrigin"):
    """Synthesize a circular footprint (metric) for a point caster that only
    carries a canopy radius — keeps the polygon path usable for trees/plants
    marked as points rather than drawn perimeters."""
    if not _HAVE_SHAPELY:
        return None
    x, y = origin.to_xy(lng, lat)
    return Point(x, y).buffer(max(0.5, float(radius_m)))


# ── Core shadow algorithm ─────────────────────────────────────────────────────

def _is_convex(poly) -> bool:
    """True when ``poly`` is (near-)convex — its area matches its convex hull's.
    Lets the swept-region builder take the cheap exact path for convex
    footprints (the common building/canopy case)."""
    try:
        hull = poly.convex_hull
        if hull.area <= 0:
            return True
        return (hull.area - poly.area) <= 1e-9 * hull.area
    except Exception:  # noqa: BLE001
        return False


def _swept_region(poly, dx, dy):
    """Exact region a footprint sweeps when translated by ``(dx, dy)`` — the
    Minkowski sum of ``poly`` with the segment ``[(0,0), (dx,dy)]``.

    For a convex footprint this equals ``convex_hull(P ∪ P+v)`` (cheap path).
    For a concave footprint the hull would wrongly fill its notches, so we union
    the footprint, its translate, and the parallelogram strip swept by every
    boundary edge (exterior + any holes) — the geometrically exact shadow
    silhouette."""
    shifted = affinity.translate(poly, xoff=dx, yoff=dy)
    if _is_convex(poly):
        return unary_union([poly, shifted]).convex_hull
    parts = [poly, shifted]
    rings = [poly.exterior]
    rings.extend(poly.interiors)
    for ring in rings:
        coords = list(ring.coords)
        for (ax, ay), (bx, by) in zip(coords, coords[1:]):
            quad = Polygon([(ax, ay), (bx, by),
                            (bx + dx, by + dy), (ax + dx, ay + dy)])
            if not quad.is_valid:
                quad = quad.buffer(0)
            if not quad.is_empty:
                parts.append(quad)
    swept = unary_union(parts)
    if not swept.is_valid:
        swept = swept.buffer(0)
    return swept


def cast_shadow(polygon, height_m: float, azimuth: float, altitude: float):
    """Cast a single footprint ``polygon`` (metric shapely Polygon) into its
    ground shadow for a sun at ``azimuth``/``altitude`` (degrees).

    The shadow is the region the footprint sweeps as it is translated down-sun
    by ``height / tan(altitude)`` (clamped to ``_MAX_SHADOW_M``) — the exact
    Minkowski-sum silhouette (see ``_swept_region``), so concave footprints
    (L-shaped buildings, courtyards) keep their notches instead of being filled
    in by a convex hull. Returns an empty/None geometry when the sun is below
    ``_MIN_SUN_ALT`` (no useful shadow, and ``1/tan`` blows up) or inputs are
    unusable."""
    if not _HAVE_SHAPELY or polygon is None or polygon.is_empty:
        return None
    if altitude < _MIN_SUN_ALT or height_m <= 0:
        return None
    shadow_len = min(height_m / math.tan(math.radians(altitude)), _MAX_SHADOW_M)
    # Shadow points away from the sun. Azimuth is degrees CW from north, so the
    # down-sun direction decomposes as east = sin, north = cos.
    shadow_dir = math.radians((azimuth + 180.0) % 360.0)
    dx = shadow_len * math.sin(shadow_dir)
    dy = shadow_len * math.cos(shadow_dir)
    try:
        swept = _swept_region(polygon, dx, dy)
    except Exception:  # noqa: BLE001
        return None
    return swept if (swept and not swept.is_empty) else None


def union_shadows(metric_casters: list, azimuth: float, altitude: float):
    """Union the shadows of every caster for one sun moment. ``metric_casters``
    is a list of ``(polygon, height_m)`` tuples (metric footprints). Returns a
    single (Multi)Polygon, or ``None`` when nothing casts."""
    if not _HAVE_SHAPELY:
        return None
    shadows = []
    for poly, height_m in metric_casters:
        shp = cast_shadow(poly, height_m, azimuth, altitude)
        if shp is not None and not shp.is_empty:
            shadows.append(shp)
    if not shadows:
        return None
    try:
        return unary_union(shadows)
    except Exception:  # noqa: BLE001
        return None


def rasterize_to_grid(shadow_geom, elev: dict,
                      origin: "_MetricOrigin") -> Optional[list]:
    """Rasterize ``shadow_geom`` (metric) onto the elevation grid: a ``[[0/1]]``
    grid (same shape as ``elev['grid']``, row 0 = north) where a cell is 1.0 iff
    its centre lies inside the shadow. Returns ``None`` when shapely is absent or
    there is nothing to draw, so the caller can fall back."""
    if not _HAVE_SHAPELY or shadow_geom is None or shadow_geom.is_empty:
        return None
    grid = elev.get("grid") or []
    rows = elev.get("rows", len(grid))
    cols = elev.get("cols", len(grid[0]) if grid else 0)
    if rows == 0 or cols == 0:
        return None
    bbox = elev["bbox"]
    out = [[0.0] * cols for _ in range(rows)]
    prepared = prep(shadow_geom)            # fast repeated point-in-polygon
    for r in range(rows):
        t = r / max(1, rows - 1)
        lat = bbox["north"] - t * (bbox["north"] - bbox["south"])
        for c in range(cols):
            u = c / max(1, cols - 1)
            lng = bbox["west"] + u * (bbox["east"] - bbox["west"])
            x, y = origin.to_xy(lng, lat)
            if prepared.contains(Point(x, y)):
                out[r][c] = 1.0
    return out


def shade_increment_for_moment(casters: list, elev: dict,
                               azimuth: float, altitude: float
                               ) -> Optional[list]:
    """End-to-end helper for one sun moment: build metric footprints for every
    caster, union their shadows, and rasterize onto ``elev``. ``casters`` are
    the dicts produced by ``shade._caster`` (carrying ``lat``/``lng``/
    ``height_m`` and either a ``footprint`` ring or a ``radius_m``). Returns a
    ``[[0/1]]`` grid, or ``None`` when shapely is unavailable / nothing casts so
    ``shade.py`` can fall back to the circle model."""
    if not _HAVE_SHAPELY or not casters:
        return None
    origin = origin_for_bbox(elev["bbox"])
    metric: list = []
    for cv in casters:
        height_m = cv.get("height_m", 0.0)
        if height_m <= 0:
            continue
        ring = cv.get("footprint")
        if ring:
            poly = footprint_to_metric(ring, origin)
        else:
            poly = point_footprint_metric(cv["lng"], cv["lat"],
                                          cv.get("radius_m", 0.5), origin)
        if poly is not None and not poly.is_empty:
            metric.append((poly, height_m))
    if not metric:
        return None
    union = union_shadows(metric, azimuth, altitude)
    return rasterize_to_grid(union, elev, origin)
