"""
projection.py — Lat/lng ↔ local-metre projection with a UTM upgrade path.

PermaDesign's distance and area maths historically used an ad-hoc
equirectangular ("cosLat") approximation: one degree of latitude is
~111,320 m everywhere, and one degree of longitude is that scaled by
cos(latitude). That's accurate to ~1% over spans under a couple of km
at Alberta latitudes — fine for a single property, loose for anything
larger.

This module centralises that maths behind a :class:`Projector` and adds
an optional, more accurate UTM backend (via ``pyproj``). The backend is
chosen by a per-project flag and degrades gracefully:

  • backend "coslat" (DEFAULT): the exact legacy formulas, so existing
    designs and tests are byte-for-byte unchanged.
  • backend "utm": auto-selects the UTM zone from the projection origin
    and uses pyproj's geodetic transform. If pyproj isn't installed it
    silently falls back to coslat — so turning the flag on can never
    crash an install that lacks the optional dependency.

The default stays "coslat" for one release cycle (per CLAUDE.md's note
on the planned migration); the app/agent layer opts a project into UTM
via :func:`set_default_backend` / the ``use_utm_projection`` project
flag once it's been validated in the field.
"""

from __future__ import annotations

import math
from typing import Optional

# Metres per degree of latitude (WGS-84 mean) — the legacy constant. Public so
# other modules (shade, property_data) share one source of truth instead of
# re-inlining the literal.
M_PER_DEG_LAT = 111320.0
_M_PER_DEG_LAT = M_PER_DEG_LAT  # internal alias kept for existing references

_BACKENDS = ("coslat", "utm")
_default_backend = "coslat"


# ── pyproj availability + UTM zone maths (pure, no pyproj needed) ───────────

def pyproj_available() -> bool:
    """True if the optional ``pyproj`` dependency can be imported."""
    try:
        import pyproj  # noqa: F401
        return True
    except Exception:
        return False


def utm_zone_for(lng: float) -> int:
    """UTM zone number (1–60) for a longitude."""
    zone = int((lng + 180.0) / 6.0) + 1
    return max(1, min(60, zone))


def utm_epsg_for(lat: float, lng: float) -> int:
    """EPSG code of the UTM CRS covering ``(lat, lng)``.

    326xx for the northern hemisphere, 327xx for the southern.
    Alberta sits in zones 11–12 N (EPSG:32611 / 32612).
    """
    zone = utm_zone_for(lng)
    return (32600 if lat >= 0 else 32700) + zone


# ── Default-backend control ─────────────────────────────────────────────────

def get_default_backend() -> str:
    """Current default projection backend ('coslat' or 'utm')."""
    return _default_backend


def set_default_backend(name: str) -> str:
    """Set the default backend used when a Projector isn't given one.

    Returns the backend that will actually be used — requesting 'utm'
    without pyproj installed resolves to 'coslat'. Raises ValueError for
    an unknown name.
    """
    global _default_backend
    if name not in _BACKENDS:
        raise ValueError(f"unknown backend {name!r}; expected one of {_BACKENDS}")
    if name == "utm" and not pyproj_available():
        _default_backend = "coslat"
    else:
        _default_backend = name
    return _default_backend


def project_uses_utm(project: dict) -> bool:
    """Read the per-project ``use_utm_projection`` flag (default False)."""
    try:
        return bool(project.get("properties", {}).get("use_utm_projection"))
    except AttributeError:
        return False


# ── Projector ────────────────────────────────────────────────────────────────

class Projector:
    """Convert between WGS-84 lat/lng and local metres about an origin.

    Construct with an origin ``(lat0, lng0)`` — typically a design's
    boundary centroid. ``to_xy`` returns metres east / north of a datum;
    for the coslat backend the datum is the origin (so the origin maps to
    (0, 0)); for the utm backend it's the zone's false-easting/northing
    (real UTM coordinates). Either way, *relative* distances between
    points are what callers use, and those are accurate.
    """

    def __init__(self, lat0: float, lng0: float,
                 backend: Optional[str] = None):
        self.lat0 = lat0
        self.lng0 = lng0
        requested = backend or _default_backend
        if requested == "utm" and pyproj_available():
            self.backend = "utm"
            from pyproj import Transformer
            epsg = utm_epsg_for(lat0, lng0)
            # always_xy → (lng, lat) order in, (easting, northing) out.
            self._fwd = Transformer.from_crs(4326, epsg, always_xy=True)
            self._inv = Transformer.from_crs(epsg, 4326, always_xy=True)
        else:
            self.backend = "coslat"
            cos_lat = math.cos(math.radians(lat0))
            self._cos_lat = cos_lat if abs(cos_lat) > 1e-9 else 1e-9

    @classmethod
    def for_positions(cls, positions: list, backend: Optional[str] = None) -> "Projector":
        """Build a Projector with its origin at the centroid of
        ``positions`` (a list of ``(lat, lng)`` pairs). Empty list →
        origin at (0, 0)."""
        if not positions:
            return cls(0.0, 0.0, backend)
        lat0 = sum(p[0] for p in positions) / len(positions)
        lng0 = sum(p[1] for p in positions) / len(positions)
        return cls(lat0, lng0, backend)

    def to_xy(self, lat: float, lng: float) -> tuple[float, float]:
        """Project ``(lat, lng)`` to ``(x_metres, y_metres)``."""
        if self.backend == "utm":
            x, y = self._fwd.transform(lng, lat)
            return x, y
        x = (lng - self.lng0) * _M_PER_DEG_LAT * self._cos_lat
        y = (lat - self.lat0) * _M_PER_DEG_LAT
        return x, y

    def to_latlng(self, x: float, y: float) -> tuple[float, float]:
        """Inverse of :meth:`to_xy`."""
        if self.backend == "utm":
            lng, lat = self._inv.transform(x, y)
            return lat, lng
        lng = self.lng0 + x / (_M_PER_DEG_LAT * self._cos_lat)
        lat = self.lat0 + y / _M_PER_DEG_LAT
        return lat, lng

    def project_many(self, positions: list) -> list[tuple[float, float]]:
        """Project a list of ``(lat, lng)`` pairs to local ``(x, y)``."""
        return [self.to_xy(lat, lng) for lat, lng in positions]

    def distance_m(self, lat1: float, lng1: float,
                   lat2: float, lng2: float) -> float:
        """Planar distance in metres between two lat/lng points under this
        projection."""
        x1, y1 = self.to_xy(lat1, lng1)
        x2, y2 = self.to_xy(lat2, lng2)
        return math.hypot(x2 - x1, y2 - y1)


# ── Module-level conveniences (back-compat for terrain/polyculture) ─────────

def metres_per_deg(lat: float, backend: Optional[str] = None) -> tuple[float, float]:
    """Approx ``(m_per_deg_lat, m_per_deg_lng)`` at ``lat``.

    The coslat backend returns the exact legacy tuple
    ``(111320, 111320*cos(lat))``. The utm backend measures the local
    scale by projecting a 0.001° step in each axis around ``(lat, 0)`` —
    which is what makes bbox/area maths track the true projection.
    """
    requested = backend or _default_backend
    if requested == "utm" and pyproj_available():
        proj = Projector(lat, 0.0, backend="utm")
        eps = 0.001
        m_lat = proj.distance_m(lat, 0.0, lat + eps, 0.0) / eps
        m_lng = proj.distance_m(lat, 0.0, lat, 0.0 + eps) / eps
        return m_lat, m_lng
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9
    return _M_PER_DEG_LAT, _M_PER_DEG_LAT * cos_lat


def to_local_xy(positions: list, backend: Optional[str] = None) -> list[tuple[float, float]]:
    """Project ``[lat, lng]`` positions into local metres about their
    centroid. The coslat backend reproduces the legacy formula's
    *relative* geometry (identical pairwise distances), so the
    polyculture layout optimiser is unaffected when the default backend
    is coslat."""
    if not positions:
        return []
    proj = Projector.for_positions(positions, backend)
    return proj.project_many(positions)
