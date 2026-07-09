"""
projection.py — Lat/lng ↔ local-metre projection (single source of truth).

Site & Pattern's distance and area maths uses an equirectangular
("cosLat") approximation: one degree of latitude is ~111,320 m
everywhere, and one degree of longitude is that scaled by cos(latitude).
That's accurate to ~1% over spans under a couple of km at prairie
latitudes — and the app designs single properties, where the error is
centimetres. This module centralises that maths behind :class:`Projector`
so no caller re-inlines the constants; the ~1% error bar is part of the
module's contract, shipped openly rather than behind a geodesy stack.

History: V1.x carried a parallel pyproj/UTM backend behind a per-project
``use_utm_projection`` flag "for one release cycle". No code path ever
enabled it, frozen builds didn't ship pyproj, and every function paid the
dual-branch tax — it was deleted in V2.22. If genuinely large sites ever
become a use case, reintroduce an alternative backend *behind this same
Projector interface*; that seam is the part worth keeping.
"""

from __future__ import annotations

import math

# Metres per degree of latitude (WGS-84 mean). Public so other modules
# (shade, property_data, succession) share one source of truth instead of
# re-inlining the literal.
M_PER_DEG_LAT = 111320.0
_M_PER_DEG_LAT = M_PER_DEG_LAT  # internal alias kept for existing references


class Projector:
    """Convert between WGS-84 lat/lng and local metres about an origin.

    Construct with an origin ``(lat0, lng0)`` — typically a design's
    boundary centroid. ``to_xy`` returns metres east / north of the
    origin (which maps to ``(0, 0)``); *relative* distances between
    points are what callers use, and those are accurate.
    """

    def __init__(self, lat0: float, lng0: float):
        self.lat0 = lat0
        self.lng0 = lng0
        cos_lat = math.cos(math.radians(lat0))
        self._cos_lat = cos_lat if abs(cos_lat) > 1e-9 else 1e-9

    @classmethod
    def for_positions(cls, positions: list) -> "Projector":
        """Build a Projector with its origin at the centroid of
        ``positions`` (a list of ``(lat, lng)`` pairs). Empty list →
        origin at (0, 0)."""
        if not positions:
            return cls(0.0, 0.0)
        lat0 = sum(p[0] for p in positions) / len(positions)
        lng0 = sum(p[1] for p in positions) / len(positions)
        return cls(lat0, lng0)

    def to_xy(self, lat: float, lng: float) -> tuple[float, float]:
        """Project ``(lat, lng)`` to ``(x_metres, y_metres)``."""
        x = (lng - self.lng0) * _M_PER_DEG_LAT * self._cos_lat
        y = (lat - self.lat0) * _M_PER_DEG_LAT
        return x, y

    def to_latlng(self, x: float, y: float) -> tuple[float, float]:
        """Inverse of :meth:`to_xy`."""
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


# ── Module-level conveniences (terrain / polyculture / scene callers) ────────

def metres_per_deg(lat: float) -> tuple[float, float]:
    """Approx ``(m_per_deg_lat, m_per_deg_lng)`` at ``lat``."""
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9
    return _M_PER_DEG_LAT, _M_PER_DEG_LAT * cos_lat


def to_local_xy(positions: list) -> list[tuple[float, float]]:
    """Project ``[lat, lng]`` positions into local metres about their
    centroid."""
    if not positions:
        return []
    return Projector.for_positions(positions).project_many(positions)
