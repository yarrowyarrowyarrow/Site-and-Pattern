"""
tests/test_projection.py

Tests for src/projection.py — the single cosLat lat/lng ↔ local-metre
layer. What matters: the maths reproduces the legacy formulas exactly
(terrain bbox sizing and the polyculture optimiser are byte-for-byte
unchanged), and the Projector round-trips.

History: until V2.22 this module also carried a pyproj/UTM backend behind
a per-project flag. No code path ever enabled it, so it was deleted; if a
new backend ever returns it must slot in behind the same Projector
interface, and these legacy-identity tests still apply to the default.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.projection import (  # noqa: E402
    M_PER_DEG_LAT,
    Projector,
    metres_per_deg,
    to_local_xy,
)

_EDM_LAT, _EDM_LNG = 53.5461, -113.4938


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


class TestMatchesLegacyMaths(unittest.TestCase):
    """The projection must not move any numbers."""

    def test_constant_exported(self):
        self.assertEqual(M_PER_DEG_LAT, 111320.0)

    def test_metres_per_deg_identical(self):
        for lat in (0.0, 53.5461, 60.0, -33.87, 89.0):
            self.assertEqual(metres_per_deg(lat), _legacy_metres_per_deg(lat))

    def test_metres_per_deg_high_lat_guard(self):
        # Near the pole cos→0; both clamp identically.
        self.assertEqual(metres_per_deg(90.0), _legacy_metres_per_deg(90.0))

    def test_to_local_xy_preserves_pairwise_distances(self):
        positions = [
            (53.5461, -113.4938), (53.5470, -113.4920),
            (53.5455, -113.4950), (53.5462, -113.4930),
        ]
        new = to_local_xy(positions)
        old = _legacy_to_local_xy(positions)
        # Absolute coords differ (centroid- vs origin-relative) but every
        # pairwise distance — all the optimiser ever uses — is identical.
        for dn, do in zip(_pairwise(new), _pairwise(old)):
            self.assertAlmostEqual(dn, do, places=6)

    def test_to_local_xy_empty(self):
        self.assertEqual(to_local_xy([]), [])


class TestProjector(unittest.TestCase):

    def test_origin_maps_to_zero(self):
        p = Projector(_EDM_LAT, _EDM_LNG)
        x, y = p.to_xy(_EDM_LAT, _EDM_LNG)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_round_trip(self):
        p = Projector(_EDM_LAT, _EDM_LNG)
        for lat, lng in [(53.55, -113.49), (53.54, -113.50)]:
            x, y = p.to_xy(lat, lng)
            rlat, rlng = p.to_latlng(x, y)
            self.assertAlmostEqual(lat, rlat, places=9)
            self.assertAlmostEqual(lng, rlng, places=9)

    def test_distance_one_degree_lat(self):
        p = Projector(_EDM_LAT, _EDM_LNG)
        d = p.distance_m(53.0, -113.5, 54.0, -113.5)
        self.assertAlmostEqual(d, 111320.0, delta=1.0)

    def test_for_positions_centroid_origin(self):
        positions = [(53.0, -113.0), (54.0, -114.0)]
        p = Projector.for_positions(positions)
        self.assertAlmostEqual(p.lat0, 53.5)
        self.assertAlmostEqual(p.lng0, -113.5)

    def test_polar_origin_clamped(self):
        # cos(90°)→0 would divide by zero on the inverse; the clamp holds.
        p = Projector(90.0, 0.0)
        x, y = p.to_xy(89.999, 0.001)
        self.assertTrue(math.isfinite(x) and math.isfinite(y))


if __name__ == "__main__":
    unittest.main()
