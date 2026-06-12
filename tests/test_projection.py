"""
tests/test_projection.py

Tests for src/projection.py — the cosLat ↔ UTM projection layer (Chunk 8).

Two things matter most:
  1. The DEFAULT (coslat) backend reproduces the legacy maths exactly, so
     terrain bbox sizing and the polyculture optimiser are byte-for-byte
     unchanged. These tests run everywhere (no pyproj needed).
  2. When pyproj IS available, the utm backend agrees with coslat to
     within ~1% for spans under 2 km at Alberta latitudes — the bound
     CLAUDE.md cites for the legacy approximation. These tests
     skipUnless(pyproj).
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import projection  # noqa: E402
from src.projection import (  # noqa: E402
    Projector,
    metres_per_deg,
    to_local_xy,
    utm_zone_for,
    utm_epsg_for,
    pyproj_available,
    set_default_backend,
    get_default_backend,
    project_uses_utm,
)

_EDM_LAT, _EDM_LNG = 53.5461, -113.4938
_HAVE_PYPROJ = pyproj_available()


def _legacy_metres_per_deg(lat):
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-9:
        cos_lat = 1e-9
    return 111320.0, 111320.0 * cos_lat


def _legacy_to_local_xy(positions):
    """The pre-Chunk-8 polyculture formula (absolute coords)."""
    if not positions:
        return []
    mean_lat = sum(p[0] for p in positions) / len(positions)
    cos_lat = math.cos(math.radians(mean_lat))
    return [(lng * 111320.0 * cos_lat, lat * 111320.0) for lat, lng in positions]


def _pairwise(pts):
    out = []
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            out.append(math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]))
    return out


class TestUtmZoneMaths(unittest.TestCase):
    """Pure number theory — no pyproj required."""

    def test_edmonton_zone_12n(self):
        self.assertEqual(utm_zone_for(_EDM_LNG), 12)
        self.assertEqual(utm_epsg_for(_EDM_LAT, _EDM_LNG), 32612)

    def test_zone_boundaries(self):
        self.assertEqual(utm_zone_for(-180.0), 1)
        self.assertEqual(utm_zone_for(179.9), 60)
        self.assertEqual(utm_zone_for(0.0), 31)

    def test_southern_hemisphere_epsg(self):
        # Sydney ~ -33.87, 151.2 → zone 56 S → 32756
        self.assertEqual(utm_epsg_for(-33.87, 151.2), 32756)


class TestDefaultBackend(unittest.TestCase):

    def setUp(self):
        self._saved = get_default_backend()

    def tearDown(self):
        # Never leak a non-default backend into other test modules.
        projection._default_backend = self._saved

    def test_default_is_coslat(self):
        self.assertEqual(get_default_backend(), "coslat")

    def test_set_unknown_raises(self):
        with self.assertRaises(ValueError):
            set_default_backend("mercator")

    def test_set_utm_falls_back_without_pyproj(self):
        resolved = set_default_backend("utm")
        if _HAVE_PYPROJ:
            self.assertEqual(resolved, "utm")
        else:
            self.assertEqual(resolved, "coslat")

    def test_project_uses_utm_flag(self):
        self.assertFalse(project_uses_utm({"properties": {}}))
        self.assertFalse(project_uses_utm({}))
        self.assertTrue(project_uses_utm(
            {"properties": {"use_utm_projection": True}}
        ))


class TestCosLatBackendMatchesLegacy(unittest.TestCase):
    """The default path must not move any numbers."""

    def test_metres_per_deg_identical(self):
        for lat in (0.0, 53.5461, 60.0, -33.87, 89.0):
            self.assertEqual(metres_per_deg(lat, backend="coslat"),
                             _legacy_metres_per_deg(lat))

    def test_metres_per_deg_high_lat_guard(self):
        # Near the pole cos→0; both clamp identically.
        self.assertEqual(metres_per_deg(90.0, backend="coslat"),
                         _legacy_metres_per_deg(90.0))

    def test_to_local_xy_preserves_pairwise_distances(self):
        positions = [
            (53.5461, -113.4938), (53.5470, -113.4920),
            (53.5455, -113.4950), (53.5462, -113.4930),
        ]
        new = to_local_xy(positions, backend="coslat")
        old = _legacy_to_local_xy(positions)
        # Absolute coords differ (centroid- vs origin-relative) but every
        # pairwise distance — all the optimiser ever uses — is identical.
        for dn, do in zip(_pairwise(new), _pairwise(old)):
            self.assertAlmostEqual(dn, do, places=6)

    def test_to_local_xy_empty(self):
        self.assertEqual(to_local_xy([]), [])


class TestProjectorCosLat(unittest.TestCase):

    def test_origin_maps_to_zero(self):
        p = Projector(_EDM_LAT, _EDM_LNG, backend="coslat")
        x, y = p.to_xy(_EDM_LAT, _EDM_LNG)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_round_trip(self):
        p = Projector(_EDM_LAT, _EDM_LNG, backend="coslat")
        for lat, lng in [(53.55, -113.49), (53.54, -113.50)]:
            x, y = p.to_xy(lat, lng)
            rlat, rlng = p.to_latlng(x, y)
            self.assertAlmostEqual(lat, rlat, places=9)
            self.assertAlmostEqual(lng, rlng, places=9)

    def test_distance_one_degree_lat(self):
        p = Projector(_EDM_LAT, _EDM_LNG, backend="coslat")
        d = p.distance_m(53.0, -113.5, 54.0, -113.5)
        self.assertAlmostEqual(d, 111320.0, delta=1.0)

    def test_for_positions_centroid_origin(self):
        positions = [(53.0, -113.0), (54.0, -114.0)]
        p = Projector.for_positions(positions, backend="coslat")
        self.assertAlmostEqual(p.lat0, 53.5)
        self.assertAlmostEqual(p.lng0, -113.5)


@unittest.skipUnless(_HAVE_PYPROJ, "pyproj not installed")
class TestUtmAgreesWithCosLat(unittest.TestCase):
    """The whole point of the migration: UTM is the accurate backend, and
    it agrees with the cosLat approximation to within ~1% for short
    spans — proving the legacy maths was 'good enough' locally and the
    UTM path isn't wildly different."""

    def _short_pairs(self):
        # All within ~2 km of the Edmonton origin.
        return [
            ((53.5461, -113.4938), (53.5470, -113.4920)),  # ~180 m
            ((53.5461, -113.4938), (53.5550, -113.4938)),  # ~1 km N
            ((53.5461, -113.4938), (53.5461, -113.4790)),  # ~1 km E
            ((53.5400, -113.5000), (53.5550, -113.4800)),  # ~2 km diagonal
        ]

    def test_distances_within_one_percent(self):
        cos = Projector(_EDM_LAT, _EDM_LNG, backend="coslat")
        utm = Projector(_EDM_LAT, _EDM_LNG, backend="utm")
        self.assertEqual(utm.backend, "utm")
        for (a, b) in self._short_pairs():
            dc = cos.distance_m(a[0], a[1], b[0], b[1])
            du = utm.distance_m(a[0], a[1], b[0], b[1])
            rel = abs(dc - du) / du
            self.assertLess(rel, 0.01, f"{a}->{b}: cos={dc:.2f} utm={du:.2f} rel={rel:.4f}")

    def test_utm_round_trip(self):
        utm = Projector(_EDM_LAT, _EDM_LNG, backend="utm")
        for lat, lng in [(53.55, -113.49), (53.54, -113.50)]:
            x, y = utm.to_xy(lat, lng)
            rlat, rlng = utm.to_latlng(x, y)
            self.assertAlmostEqual(lat, rlat, places=6)
            self.assertAlmostEqual(lng, rlng, places=6)

    def test_metres_per_deg_utm_close_to_coslat(self):
        m_lat_u, m_lng_u = metres_per_deg(_EDM_LAT, backend="utm")
        m_lat_c, m_lng_c = metres_per_deg(_EDM_LAT, backend="coslat")
        self.assertLess(abs(m_lat_u - m_lat_c) / m_lat_c, 0.01)
        self.assertLess(abs(m_lng_u - m_lng_c) / m_lng_c, 0.01)


if __name__ == "__main__":
    unittest.main()
