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
class TestConcaveSweptRegion(unittest.TestCase):
    """V1.53 — the exact Minkowski-sum swept region keeps concave footprints'
    notches instead of filling them with a convex hull."""

    def _L(self):
        from shapely.geometry import Polygon
        # An L-shape (clearly concave): a 4x4 square with the top-right cut out.
        return Polygon([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)])

    def test_is_convex_detection(self):
        from shapely.geometry import Polygon
        square = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        self.assertTrue(sg._is_convex(square))
        self.assertFalse(sg._is_convex(self._L()))

    def test_concave_swept_smaller_than_hull(self):
        # Translate straight north by 2 m: the exact swept region must be
        # smaller than its convex hull (the hull fills the L's notch).
        L = self._L()
        swept = sg._swept_region(L, 0.0, 2.0)
        self.assertTrue(swept.is_valid)
        self.assertLess(swept.area, swept.convex_hull.area - 1e-6)
        # And it must cover at least the footprint plus its translate.
        from shapely import affinity
        from shapely.ops import unary_union
        lo = unary_union([L, affinity.translate(L, yoff=2.0)])
        self.assertGreaterEqual(swept.area, lo.area - 1e-6)

    def test_convex_swept_equals_hull(self):
        from shapely.geometry import Polygon
        square = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
        swept = sg._swept_region(square, 1.0, 3.0)
        self.assertAlmostEqual(swept.area, swept.convex_hull.area, places=6)

    def test_cast_shadow_concave_valid(self):
        L = self._L()
        shadow = sg.cast_shadow(L, height_m=2.0, azimuth=180.0, altitude=45.0)
        self.assertIsNotNone(shadow)
        self.assertTrue(shadow.is_valid)
        self.assertLess(shadow.area, shadow.convex_hull.area - 1e-6)


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


@unittest.skipUnless(sg._HAVE_SHAPELY, "shapely not installed")
class TestTrueShapeVsCircle(unittest.TestCase):
    """A real building footprint casts its true outline, not a round blob —
    the core of the V1.58 fix for OSM buildings that used to be circles."""

    def setUp(self):
        self.origin = sg.origin_for_bbox(_BBOX)

    def _rect_ring(self, half_w_m, half_h_m):
        dlat = half_h_m / 111320.0
        dlng = half_w_m / (111320.0 * math.cos(math.radians(_CLAT)))
        return [(_CLNG - dlng, _CLAT - dlat), (_CLNG + dlng, _CLAT - dlat),
                (_CLNG + dlng, _CLAT + dlat), (_CLNG - dlng, _CLAT + dlat),
                (_CLNG - dlng, _CLAT - dlat)]

    def test_wide_rectangle_keeps_its_aspect(self):
        # A wide, shallow building (10 m × 2 m). A high southern sun throws the
        # shadow north; the silhouette must stay much wider (E-W) than it is
        # deep (N-S) — a circle would be ~symmetric.
        poly = sg.footprint_to_metric(self._rect_ring(5.0, 1.0), self.origin)
        shadow = sg.cast_shadow(poly, height_m=4.0, azimuth=180.0, altitude=60.0)
        self.assertIsNotNone(shadow)
        minx, miny, maxx, maxy = shadow.bounds
        self.assertGreater(maxx - minx, maxy - miny)   # wider than deep
        self.assertGreater(maxx - minx, 9.0)           # ~10 m width preserved

    def test_polygon_shadow_differs_from_point_circle(self):
        # Same spot / height / sun: a true rectangle footprint and a point
        # (radius circle) caster produce different silhouettes — proving the
        # polygon path is not the old circle blob.
        poly = sg.footprint_to_metric(self._rect_ring(5.0, 1.0), self.origin)
        rect_shadow = sg.cast_shadow(poly, 4.0, 180.0, 60.0)
        circ = sg.point_footprint_metric(_CLNG, _CLAT, 2.0, self.origin)
        circ_shadow = sg.cast_shadow(circ, 4.0, 180.0, 60.0)
        self.assertIsNotNone(rect_shadow)
        self.assertIsNotNone(circ_shadow)
        rw = rect_shadow.bounds[2] - rect_shadow.bounds[0]
        cw = circ_shadow.bounds[2] - circ_shadow.bounds[0]
        self.assertGreater(rw, cw)                      # rectangle is wider


class TestMetricRoundTrip(unittest.TestCase):
    """V1.54 — the inverse projection used to draw vector shadows back on the
    map must round-trip with the forward transform."""

    def test_to_xy_to_lnglat_round_trip(self):
        origin = sg.origin_for_bbox(_BBOX)
        for lng, lat in [(_CLNG, _CLAT),
                         (_BBOX["west"], _BBOX["south"]),
                         (_BBOX["east"], _BBOX["north"])]:
            x, y = origin.to_xy(lng, lat)
            lng2, lat2 = origin.to_lnglat(x, y)
            self.assertAlmostEqual(lng, lng2, places=9)
            self.assertAlmostEqual(lat, lat2, places=9)

    def test_origin_maps_to_zero(self):
        origin = sg.origin_for_bbox(_BBOX)
        x, y = origin.to_xy(_BBOX["west"], _BBOX["south"])
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)


@unittest.skipUnless(sg._HAVE_SHAPELY, "shapely not installed")
class TestLatLngRings(unittest.TestCase):
    """V1.54 — projecting metric shadow polygons back to [lat,lng] rings for the
    Leaflet vector overlay."""

    def setUp(self):
        self.origin = sg.origin_for_bbox(_BBOX)
        self.poly = sg.footprint_to_metric(
            _square_ring(_CLAT, _CLNG, 2.0), self.origin)

    def test_rings_shape_and_location(self):
        shadow = sg.cast_shadow(self.poly, 10.0, 180.0, 45.0)
        polys = sg.latlng_rings(shadow, self.origin)
        self.assertTrue(polys)                       # at least one polygon
        ext = polys[0][0]                            # first polygon, exterior
        self.assertGreaterEqual(len(ext), 4)
        # Every vertex is a [lat, lng] pair near the site.
        for lat, lng in ext:
            self.assertAlmostEqual(lat, _CLAT, delta=0.01)
            self.assertAlmostEqual(lng, _CLNG, delta=0.01)
        # Shadow extends north of the footprint centre (southern sun).
        self.assertGreater(max(p[0] for p in ext), _CLAT)

    def test_empty_geometry_returns_empty(self):
        self.assertEqual(sg.latlng_rings(None, self.origin), [])

    def test_concave_hole_preserved(self):
        from shapely.geometry import Polygon
        # A square with a square hole → one polygon with an exterior + a hole.
        outer = [(0, 0), (20, 0), (20, 20), (0, 20)]
        hole = [(5, 5), (5, 15), (15, 15), (15, 5)]
        poly = Polygon(outer, [hole])
        polys = sg.latlng_rings(poly, self.origin)
        self.assertEqual(len(polys), 1)
        self.assertEqual(len(polys[0]), 2)           # exterior + 1 hole

    def test_union_geometries_folds_moments(self):
        a = sg.cast_shadow(self.poly, 10.0, 180.0, 45.0)   # north
        b = sg.cast_shadow(self.poly, 10.0, 90.0, 45.0)    # west
        merged = sg.union_geometries([a, b])
        self.assertIsNotNone(merged)
        self.assertGreaterEqual(merged.area, a.area)
        self.assertGreaterEqual(merged.area, b.area)


@unittest.skipUnless(sg._HAVE_SHAPELY, "shapely not installed")
class TestCastTreeShadow(unittest.TestCase):
    """V1.59 — a tree casts a thin trunk + a canopy that tapers to the tip,
    not a building's vertical (convex) extrusion."""

    def setUp(self):
        self.origin = sg.origin_for_bbox(_BBOX)
        self.center = self.origin.to_xy(_CLNG, _CLAT)

    def test_extends_north_for_southern_sun(self):
        # Sun due south, altitude 45 (tan=1) → tip ~height north of the base.
        shadow = sg.cast_tree_shadow(self.center, radius_m=3.0, height_m=10.0,
                                     azimuth=180.0, altitude=45.0)
        self.assertIsNotNone(shadow)
        self.assertGreater(shadow.bounds[3], self.center[1] + 8.0)

    def test_low_sun_no_shadow(self):
        self.assertIsNone(
            sg.cast_tree_shadow(self.center, 3.0, 10.0, 180.0,
                                sg._MIN_SUN_ALT - 1.0))

    def test_length_clamped(self):
        shadow = sg.cast_tree_shadow(self.center, 3.0, 100.0, 180.0, 6.0)
        self.assertIsNotNone(shadow)
        self.assertLessEqual(shadow.bounds[3] - self.center[1],
                             sg._MAX_SHADOW_M + 5.0)

    def test_tapers_toward_the_tip(self):
        # A thin cross-slab near the tip is much narrower than one through the
        # crown — the canopy narrows to a point.
        from shapely.geometry import box
        shadow = sg.cast_tree_shadow(self.center, radius_m=4.0, height_m=12.0,
                                     azimuth=180.0, altitude=45.0)
        minx, miny, maxx, maxy = shadow.bounds

        def width_at(frac):
            y = miny + (maxy - miny) * frac
            inter = shadow.intersection(box(minx - 1, y - 0.05,
                                            maxx + 1, y + 0.05))
            return 0.0 if inter.is_empty else inter.bounds[2] - inter.bounds[0]

        self.assertLess(width_at(0.95), width_at(0.6))

    def test_smaller_than_building_of_equal_size(self):
        # Same height + size: the tapering tree covers less ground than the
        # building's swept extrusion of an equivalent footprint.
        tree = sg.cast_tree_shadow(self.center, radius_m=3.0, height_m=10.0,
                                   azimuth=180.0, altitude=45.0)
        bpoly = sg.footprint_to_metric(_square_ring(_CLAT, _CLNG, 3.0),
                                       self.origin)
        bldg = sg.cast_shadow(bpoly, height_m=10.0, azimuth=180.0,
                              altitude=45.0)
        self.assertIsNotNone(tree)
        self.assertIsNotNone(bldg)
        self.assertLess(tree.area, bldg.area)


if __name__ == "__main__":
    unittest.main()
