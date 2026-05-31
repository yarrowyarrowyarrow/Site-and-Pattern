"""
tests/test_shadow_geometry.py

V1.53 — the shapely footprint-polygon shadow core (src/shadow_geometry.py).
Gated on shapely being installed; the circle fallback is covered by
tests/test_shade.py with _HAVE_SHAPELY forced False.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.shadow_geometry as sg  # noqa: E402

# A small bbox near Edmonton; origin anchored at its SW corner.
_BBOX = {"north": 53.50050, "south": 53.49950,
         "east": -113.49920, "west": -113.50080}
_N = 11
_ELEV = {"grid": [[100.0] * _N for _ in range(_N)], "rows": _N, "cols": _N,
         "bbox": _BBOX}
_CLAT = (_BBOX["north"] + _BBOX["south"]) / 2
_CLNG = (_BBOX["east"] + _BBOX["west"]) / 2


def _square_ring(clat, clng, half_m):
    """A small axis-aligned square footprint (ring of lng/lat) about a centre."""
    dlat = half_m / 111320.0
    dlng = half_m / (111320.0 * math.cos(math.radians(clat)))
    return [
        (clng - dlng, clat - dlat),
        (clng + dlng, clat - dlat),
        (clng + dlng, clat + dlat),
        (clng - dlng, clat + dlat),
        (clng - dlng, clat - dlat),
    ]


@unittest.skipUnless(sg._HAVE_SHAPELY, "shapely not installed")
class TestCastShadow(unittest.TestCase):

    def setUp(self):
        self.origin = sg.origin_for_bbox(_BBOX)
        self.poly = sg.footprint_to_metric(
            _square_ring(_CLAT, _CLNG, 2.0), self.origin)

    def test_footprint_parsed(self):
        self.assertIsNotNone(self.poly)
        self.assertGreater(self.poly.area, 0.0)

    def test_shadow_extends_north_for_southern_sun(self):
        # Sun due south (az 180), altitude 45 (tan=1) → shadow extends due NORTH
        # by ~= height. The hull's north edge should exceed the footprint's.
        shadow = sg.cast_shadow(self.poly, height_m=10.0,
                                azimuth=180.0, altitude=45.0)
        self.assertIsNotNone(shadow)
        # max y (north) of shadow > max y of footprint, and area grew.
        self.assertGreater(shadow.bounds[3], self.poly.bounds[3])
        self.assertGreaterEqual(shadow.area, self.poly.area)
        # Shadow length ~ height (tan45=1): north extent grows by ~10 m.
        self.assertAlmostEqual(shadow.bounds[3] - self.poly.bounds[3],
                               10.0, delta=1.0)

    def test_low_sun_no_shadow(self):
        self.assertIsNone(
            sg.cast_shadow(self.poly, 10.0, 180.0, sg._MIN_SUN_ALT - 1.0))

    def test_shadow_length_clamped(self):
        # Very low (but valid) sun would project an enormous shadow; clamp.
        shadow = sg.cast_shadow(self.poly, height_m=100.0,
                                azimuth=180.0, altitude=6.0)
        self.assertIsNotNone(shadow)
        north_growth = shadow.bounds[3] - self.poly.bounds[3]
        self.assertLessEqual(north_growth, sg._MAX_SHADOW_M + 1.0)


@unittest.skipUnless(sg._HAVE_SHAPELY, "shapely not installed")
class TestUnionAndRasterize(unittest.TestCase):

    def setUp(self):
        self.origin = sg.origin_for_bbox(_BBOX)

    def test_union_less_than_sum_for_overlap(self):
        # Two casters at the same spot → union area < 2x a single shadow.
        poly = sg.footprint_to_metric(
            _square_ring(_CLAT, _CLNG, 2.0), self.origin)
        single = sg.cast_shadow(poly, 10.0, 180.0, 45.0)
        union = sg.union_shadows([(poly, 10.0), (poly, 10.0)], 180.0, 45.0)
        self.assertIsNotNone(union)
        self.assertLess(union.area, 2 * single.area - 1e-6)

    def test_rasterize_marks_inside_cell(self):
        poly = sg.footprint_to_metric(
            _square_ring(_CLAT, _CLNG, 2.0), self.origin)
        union = sg.union_shadows([(poly, 10.0)], 180.0, 45.0)
        grid = sg.rasterize_to_grid(union, _ELEV, self.origin)
        self.assertIsNotNone(grid)
        self.assertEqual(len(grid), _N)
        self.assertEqual(len(grid[0]), _N)
        # Something must be shaded (the centre and cells just north of it).
        self.assertTrue(any(v for row in grid for v in row))

    def test_point_caster_via_radius(self):
        # A caster with no footprint ring still casts via a buffered radius.
        casters = [{"lat": _CLAT, "lng": _CLNG, "height_m": 10.0,
                    "radius_m": 2.0}]
        grid = sg.shade_increment_for_moment(casters, _ELEV, 180.0, 45.0)
        self.assertIsNotNone(grid)
        self.assertTrue(any(v for row in grid for v in row))


if __name__ == "__main__":
    unittest.main()
