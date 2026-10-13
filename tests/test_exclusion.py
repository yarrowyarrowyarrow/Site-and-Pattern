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


class TestZoneSteering(unittest.TestCase):
    """F5 — drawn zones steer the generator: keep out of existing-remnant +
    hardscape areas; fill into restoration / lawn-conversion areas."""

    def _label(self, key):
        from src.lawn_zones import ZONE_TYPES
        return ZONE_TYPES[key]["label"]

    def test_remnant_and_hardscape_become_keepout(self):
        proj = _project(
            _poly_feature("custom_shape", _LAT, _LNG, 6.0,
                          shape_type=self._label("existing_remnant")),
            _poly_feature("custom_shape", _LAT, _LNG + 0.001, 4.0,
                          shape_type="Pathway"),
            _poly_feature("custom_shape", _LAT, _LNG + 0.002, 4.0,
                          shape_type="Patio / Deck"),
        )
        self.assertEqual(len(X.keepout_circles(proj)), 3)

    def test_plantable_shapes_are_not_keepout(self):
        # Garden bed / lawn / mulch shapes stay plantable (not avoided).
        proj = _project(
            _poly_feature("custom_shape", _LAT, _LNG, 5.0, shape_type="Garden Bed"),
            _poly_feature("custom_shape", _LAT, _LNG, 5.0, shape_type="Lawn Area"),
        )
        self.assertEqual(X.keepout_circles(proj), [])

    def test_fill_regions_returns_only_restoration_zones(self):
        proj = _project(
            _poly_feature("custom_shape", _LAT, _LNG, 5.0,
                          shape_type=self._label("restoration_year_1")),
            _poly_feature("custom_shape", _LAT, _LNG, 5.0,
                          shape_type=self._label("lawn_remaining")),
            _poly_feature("custom_shape", _LAT, _LNG, 5.0,
                          shape_type=self._label("existing_remnant")),  # not a fill
            _poly_feature("custom_shape", _LAT, _LNG, 5.0, shape_type="Pathway"),
        )
        regions = X.fill_regions(proj)
        self.assertEqual(len(regions), 2)   # the two restoration/lawn zones only

    def test_fill_regions_empty_when_none(self):
        self.assertEqual(X.fill_regions(_project()), [])


def _rect_feature(shape_type, east0, north0, east1, north1):
    """A drawn rectangle, metres east/north of (_LAT, _LNG)."""
    kx = 111320.0 * math.cos(math.radians(_LAT))
    ring = [[_LNG + e / kx, _LAT + n / 111320.0]
            for e, n in ((east0, north0), (east1, north0), (east1, north1),
                         (east0, north1), (east0, north0))]
    return {"geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "custom_shape",
                           "shape_type": shape_type}}


def _at(east, north):
    kx = 111320.0 * math.cos(math.radians(_LAT))
    return _LAT + north / 111320.0, _LNG + east / kx


class TestKeepOutIsTheShapeDrawn(unittest.TestCase):
    """V3.18 (PY-3): a drawn path was kept out as one circle about its centre
    reaching its far corner, 5 m across either side of a 1 m path."""

    def setUp(self):
        self.path = _project(_rect_feature("Pathway", 7, 0, 8, 10))
        self.keep = X.keepout_areas(self.path)

    def test_a_drawn_path_is_a_shape_not_a_circle(self):
        self.assertEqual(len(self.keep.shapes), 1)
        self.assertEqual(self.keep.circles, [])

    def test_on_the_path_is_kept_out(self):
        self.assertFalse(X.is_clear(*_at(7.5, 5.0), self.keep))
        self.assertFalse(X.is_clear(*_at(7.1, 0.2), self.keep))

    def test_beside_the_path_is_clear_though_the_old_circle_covered_it(self):
        lat, lng = _at(5.0, 5.0)                        # 2 m west of it
        self.assertFalse(X.is_clear(lat, lng, X.keepout_circles(self.path)))
        self.assertTrue(X.is_clear(lat, lng, self.keep))
        self.assertTrue(X.is_clear(*_at(9.0, 9.0), self.keep))

    def test_a_margin_keeps_a_plant_body_off_the_edge(self):
        lat, lng = _at(6.6, 5.0)                        # 0.4 m from its edge
        self.assertTrue(X.is_clear(lat, lng, self.keep))
        self.assertFalse(X.is_clear(lat, lng, self.keep, extra_margin_m=0.5))
        self.assertTrue(X.is_clear(lat, lng, self.keep, extra_margin_m=0.3))

    def test_a_building_footprint_is_its_outline(self):
        building = _poly_feature("canopy_footprint", _LAT, _LNG, 5.0,
                                 canopy_radius_m=7.1)
        keep = X.keepout_areas(_project(building))
        self.assertEqual(len(keep.shapes), 1)
        self.assertFalse(X.is_clear(_LAT, _LNG, keep))
        self.assertTrue(X.is_clear(*_at(6.0, 0.0), keep))   # past the wall

    def test_points_stay_circles(self):
        keep = X.keepout_areas(_project(
            _pt_feature("existing_tree", _LAT, _LNG, canopy_radius_m=4.0)))
        self.assertEqual(keep.circles, [(_LAT, _LNG, 4.0)])
        self.assertEqual(keep.shapes, [])

    def test_keep_outs_add_up_and_empty_is_nothing(self):
        tree = X.keepout_areas(_project(
            _pt_feature("existing_tree", _LAT, _LNG, canopy_radius_m=4.0)))
        both = self.keep + tree
        self.assertEqual((len(both.circles), len(both.shapes)), (1, 1))
        mixed = [(_LAT, _LNG, 1.0)] + self.keep
        self.assertEqual((len(mixed.circles), len(mixed.shapes)), (1, 1))
        self.assertFalse(X.keepout_areas(_project()))
        self.assertTrue(X.is_clear(_LAT, _LNG, X.keepout_areas(_project())))

    def test_the_coarse_view_still_has_every_keep_out(self):
        proj = _project(_rect_feature("Pathway", 7, 0, 8, 10),
                        _pt_feature("existing_tree", _LAT, _LNG,
                                    canopy_radius_m=4.0))
        self.assertEqual(len(X.keepout_circles(proj)), 2)


if __name__ == "__main__":
    unittest.main()
