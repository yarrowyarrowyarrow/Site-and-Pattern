"""
tests/test_layout.py

V1.50 — the plant-group layout patterns (Python ports of the JS pattern math).
Pure geometry, no DB / Qt. Verifies counts, spacing, centring, determinism, and
the type→default-pattern mapping.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.layout as L  # noqa: E402

_LAT, _LNG = 53.5, -113.5


def _dist_m(a, b):
    cl = math.cos(a[0] * math.pi / 180)
    return math.hypot((b[1] - a[1]) * 111320 * cl, (b[0] - a[0]) * 111320)


class TestRow(unittest.TestCase):
    def test_count_and_spacing(self):
        pts = L.row_positions(_LAT, _LNG, 5, 2.0)
        self.assertEqual(len(pts), 5)
        self.assertAlmostEqual(_dist_m(pts[0], pts[1]), 2.0, places=1)

    def test_centred_on_anchor(self):
        pts = L.row_positions(_LAT, _LNG, 4, 2.0)
        mid_lat = sum(p[0] for p in pts) / 4
        mid_lng = sum(p[1] for p in pts) / 4
        self.assertAlmostEqual(mid_lat, _LAT, places=6)
        self.assertAlmostEqual(mid_lng, _LNG, places=6)

    def test_single(self):
        self.assertEqual(L.row_positions(_LAT, _LNG, 1, 2.0), [(_LAT, _LNG)])


class TestGrid(unittest.TestCase):
    def test_exact_count(self):
        for n in (1, 4, 7, 9, 12):
            self.assertEqual(len(L.grid_positions(_LAT, _LNG, n, 1.5)), n)

    def test_roughly_square(self):
        pts = L.grid_positions(_LAT, _LNG, 9, 1.5, stagger=False)
        # 9 → 3×3; spans in both axes should be similar
        lat_span = (max(p[0] for p in pts) - min(p[0] for p in pts)) * 111320
        cl = math.cos(_LAT * math.pi / 180)
        lng_span = (max(p[1] for p in pts) - min(p[1] for p in pts)) * 111320 * cl
        self.assertAlmostEqual(lat_span, lng_span, delta=1.0)


class TestCircle(unittest.TestCase):
    def test_count_and_centre_first(self):
        pts = L.circle_positions(_LAT, _LNG, 7, 1.0)
        self.assertEqual(len(pts), 7)
        self.assertAlmostEqual(pts[0][0], _LAT, places=9)
        self.assertAlmostEqual(pts[0][1], _LNG, places=9)

    def test_perimeter_ring(self):
        pts = L.circle_positions(_LAT, _LNG, 6, 1.0, fill=False)
        self.assertEqual(len(pts), 6)
        # all roughly equidistant from centre
        ds = [_dist_m((_LAT, _LNG), p) for p in pts]
        self.assertAlmostEqual(min(ds), max(ds), delta=0.01)


class TestScatter(unittest.TestCase):
    def test_count_and_deterministic(self):
        a = L.scatter_positions(_LAT, _LNG, 6, 1.0, seed=42)
        b = L.scatter_positions(_LAT, _LNG, 6, 1.0, seed=42)
        self.assertEqual(len(a), 6)
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        a = L.scatter_positions(_LAT, _LNG, 6, 1.0, seed=1)
        b = L.scatter_positions(_LAT, _LNG, 6, 1.0, seed=2)
        self.assertNotEqual(a, b)


class TestDrift(unittest.TestCase):
    def test_count_and_deterministic(self):
        a = L.drift_positions(_LAT, _LNG, 12, 1.0, seed=7)
        b = L.drift_positions(_LAT, _LNG, 12, 1.0, seed=7)
        self.assertEqual(len(a), 12)
        self.assertEqual(a, b)

    def test_single(self):
        self.assertEqual(L.drift_positions(_LAT, _LNG, 1, 1.0), [(_LAT, _LNG)])

    def test_elongated(self):
        # A drift along a fixed bearing should span noticeably further along its
        # long axis than across it — that's what makes it read as a drift, not a
        # blob. Use due-east (bearing 90) so the long axis is the lng axis.
        pts = L.drift_positions(_LAT, _LNG, 40, 1.0, seed=3, bearing_deg=90.0)
        cl = math.cos(_LAT * math.pi / 180)
        along = (max(p[1] for p in pts) - min(p[1] for p in pts)) * 111320 * cl
        across = (max(p[0] for p in pts) - min(p[0] for p in pts)) * 111320
        self.assertGreater(along, across * 1.5)


class TestDispatchAndDefaults(unittest.TestCase):
    def test_dispatch_matches_direct(self):
        self.assertEqual(
            L.positions_for_layout("row", _LAT, _LNG, 3, 2.0),
            L.row_positions(_LAT, _LNG, 3, 2.0))
        self.assertEqual(
            L.positions_for_layout("drift", _LAT, _LNG, 8, 1.0),
            L.drift_positions(_LAT, _LNG, 8, 1.0))

    def test_unknown_falls_back_to_scatter(self):
        got = L.positions_for_layout("bogus", _LAT, _LNG, 4, 1.0)
        self.assertEqual(got, L.scatter_positions(_LAT, _LNG, 4, 1.0))

    def test_default_by_habit(self):
        self.assertEqual(L.default_layout_for("tree"), L.GRID)
        self.assertEqual(L.default_layout_for("shrub"), L.CIRCLE)
        self.assertEqual(L.default_layout_for("grass"), L.DRIFT)
        self.assertEqual(L.default_layout_for("groundcover"), L.ROW)
        self.assertIn(L.DRIFT, L.LAYOUTS)


if __name__ == "__main__":
    unittest.main()
