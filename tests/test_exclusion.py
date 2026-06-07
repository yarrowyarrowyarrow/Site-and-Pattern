"""
tests/test_exclusion.py

V1.50 — keep-out zones so generated plants never land on top of existing
trees/buildings or the design's own water structures. Pure geometry, no Qt/DB.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.exclusion as X  # noqa: E402

_LAT, _LNG = 53.5, -113.5


def _project(*features):
    return {"features": list(features)}


def _pt_feature(etype, lat, lng, **props):
    p = {"element_type": etype}
    p.update(props)
    return {"geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": p}


def _square_ring(lat, lng, half_m):
    dlat = half_m / 111320.0
    dlng = half_m / (111320.0 * math.cos(math.radians(lat)))
    return [[lng - dlng, lat - dlat], [lng + dlng, lat - dlat],
            [lng + dlng, lat + dlat], [lng - dlng, lat + dlat],
            [lng - dlng, lat - dlat]]


def _poly_feature(etype, clat, clng, half_m, **props):
    p = {"element_type": etype}
    p.update(props)
    return {"geometry": {"type": "Polygon",
                         "coordinates": [_square_ring(clat, clng, half_m)]},
            "properties": p}


class TestKeepoutCircles(unittest.TestCase):
    def test_existing_tree_uses_canopy_radius(self):
        proj = _project(_pt_feature("existing_tree", _LAT, _LNG,
                                    canopy_radius_m=5.0))
        circles = X.keepout_circles(proj)
        self.assertEqual(len(circles), 1)
        self.assertEqual(circles[0][2], 5.0)

    def test_existing_tree_falls_back_to_size(self):
        proj = _project(_pt_feature("existing_tree", _LAT, _LNG, size_m=8.0))
        self.assertEqual(X.keepout_circles(proj)[0][2], 4.0)   # size/2

    def test_water_structure_excludes_others_dont(self):
        proj = _project(
            _pt_feature("structure", _LAT, _LNG,
                        struct_def={"id": "pond", "size_m": 6.0}),
            _pt_feature("structure", _LAT, _LNG,
                        struct_def={"id": "bee_hotel", "size_m": 0.6}),
        )
        circles = X.keepout_circles(proj)
        self.assertEqual(len(circles), 1)        # only the pond
        self.assertEqual(circles[0][2], 3.0)     # 6 / 2

    def test_building_counted(self):
        proj = _project(_pt_feature("existing_building", _LAT, _LNG,
                                    canopy_radius_m=4.0))
        self.assertEqual(len(X.keepout_circles(proj)), 1)

    def test_plant_not_counted(self):
        proj = _project(_pt_feature("plant", _LAT, _LNG, plant_id=1))
        self.assertEqual(X.keepout_circles(proj), [])


class TestCanopyFootprintKeepout(unittest.TestCase):
    """V1.59 — any canopy_footprint polygon with a canopy_radius_m keeps planting
    out (OSM, hand-drawn building outlines, and nDSM-extracted footprints), not
    just OSM imports."""

    def test_osm_footprint_uses_stored_centroid(self):
        proj = _project(_poly_feature(
            "canopy_footprint", _LAT, _LNG, 4.0,
            source="osm", lat=_LAT, lng=_LNG, canopy_radius_m=7.1))
        circles = X.keepout_circles(proj)
        self.assertEqual(len(circles), 1)
        self.assertAlmostEqual(circles[0][0], _LAT, places=6)
        self.assertAlmostEqual(circles[0][1], _LNG, places=6)
        self.assertEqual(circles[0][2], 7.1)

    def test_drawn_footprint_derives_centroid_from_ring(self):
        # A hand-drawn building outline (no source, no stored lat/lng) must still
        # keep planting out, deriving its centroid from the ring.
        proj = _project(_poly_feature(
            "canopy_footprint", _LAT, _LNG, 5.0, canopy_radius_m=6.0))
        circles = X.keepout_circles(proj)
        self.assertEqual(len(circles), 1)
        self.assertAlmostEqual(circles[0][0], _LAT, places=5)
        self.assertAlmostEqual(circles[0][1], _LNG, places=5)
        self.assertEqual(circles[0][2], 6.0)

    def test_extracted_footprint_kept_out(self):
        proj = _project(_poly_feature(
            "canopy_footprint", _LAT, _LNG, 5.0,
            source="extract", canopy_radius_m=7.0))
        self.assertEqual(len(X.keepout_circles(proj)), 1)

    def test_plain_custom_shape_not_kept_out(self):
        # A non-casting custom_shape (no canopy_radius_m) is just an area marker.
        proj = _project(_poly_feature("custom_shape", _LAT, _LNG, 5.0))
        self.assertEqual(X.keepout_circles(proj), [])


class TestIsClear(unittest.TestCase):
    def setUp(self):
        self.circles = [(_LAT, _LNG, 10.0)]   # 10 m radius keep-out

    def test_centre_not_clear(self):
        self.assertFalse(X.is_clear(_LAT, _LNG, self.circles))

    def test_far_is_clear(self):
        # ~16 m north — outside the 10 m circle
        far_lat = _LAT + 16.0 / 111320.0
        self.assertTrue(X.is_clear(far_lat, _LNG, self.circles))

    def test_margin_pushes_out(self):
        # 11 m north is clear of the bare circle but not with a 2 m margin
        lat = _LAT + 11.0 / 111320.0
        self.assertTrue(X.is_clear(lat, _LNG, self.circles))
        self.assertFalse(X.is_clear(lat, _LNG, self.circles, extra_margin_m=2.0))

    def test_empty_circles_always_clear(self):
        self.assertTrue(X.is_clear(_LAT, _LNG, []))

    def test_filter_clear(self):
        cl = math.cos(_LAT * math.pi / 180)
        pts = [(_LAT, _LNG),                                  # at centre — out
               (_LAT + 20.0 / 111320.0, _LNG)]               # 20 m away — in
        kept = X.filter_clear(pts, self.circles)
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()
