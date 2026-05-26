"""
tests/test_ecoregion.py

Verifies the V1.36 ecoregion auto-detect via point-in-polygon against
the shipped ``data/ecoregions_canada.geojson``. Each test asserts a
real city's lat/lng resolves to the canonical ecoregion key the plant
filter expects.

The shipped starter polygon set is a rectangular partition of
Alberta — the city assertions below are calibrated against that
starter set. When a future revision replaces those rectangles with
real CEC polygons (via ``scripts/prepare_ecoregions.py``), expect
some of these assertions to need adjustment for boundary cases like
Calgary (which sits at the prairie-foothills transition).
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ecoregion import (  # noqa: E402
    lookup_ecoregion,
    label_for_key,
    _point_in_ring,
    _point_in_polygon,
    _load_features,
)


class TestLoadFeatures(unittest.TestCase):

    def test_shipped_geojson_loads(self):
        features = _load_features()
        self.assertGreaterEqual(len(features), 5,
                                "Expected at least 5 AB ecoregion features")

    def test_all_features_have_canonical_key(self):
        """Every feature's `key` must be one of the canonical keys in
        plant_panel._AB_ECOREGION_CHOICES — otherwise the auto-detect
        result wouldn't match any combo option."""
        canonical = {
            "aspen_parkland", "mixedgrass_prairie", "fescue_foothills",
            "boreal_mixedwood", "riparian", "wet_meadow",
            "subalpine_montane",
        }
        for feat in _load_features():
            key = (feat.get("properties") or {}).get("key", "")
            self.assertIn(key, canonical,
                          f"Feature key {key!r} not in canonical set")


class TestPointInRing(unittest.TestCase):
    """Sanity-check the ray-casting primitive on a known unit square."""

    SQUARE = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]

    def test_inside_centre(self):
        self.assertTrue(_point_in_ring(0.5, 0.5, self.SQUARE))

    def test_outside_left(self):
        self.assertFalse(_point_in_ring(0.5, -1, self.SQUARE))

    def test_outside_right(self):
        self.assertFalse(_point_in_ring(0.5, 2, self.SQUARE))

    def test_outside_above(self):
        self.assertFalse(_point_in_ring(2, 0.5, self.SQUARE))

    def test_outside_below(self):
        self.assertFalse(_point_in_ring(-1, 0.5, self.SQUARE))

    def test_degenerate_ring(self):
        self.assertFalse(_point_in_ring(0.5, 0.5, [[0, 0], [1, 1]]))


class TestPolygonWithHole(unittest.TestCase):

    OUTER = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    HOLE  = [[3, 3], [7, 3], [7, 7], [3, 7], [3, 3]]

    def test_inside_outer_but_in_hole(self):
        self.assertFalse(_point_in_polygon(5, 5, [self.OUTER, self.HOLE]))

    def test_inside_outer_and_not_in_hole(self):
        self.assertTrue(_point_in_polygon(1, 1, [self.OUTER, self.HOLE]))


class TestAlbertaCityLookups(unittest.TestCase):
    """Real city coordinates → expected ecoregion key. Adjust if the
    polygon set changes."""

    def assertEco(self, lat: float, lng: float, expected_key: str):
        got = lookup_ecoregion(lat, lng)
        self.assertEqual(got, expected_key,
                         f"({lat}, {lng}) → got {got!r}, expected {expected_key!r}")

    def test_edmonton_is_aspen_parkland(self):
        # Edmonton centroid
        self.assertEco(53.5461, -113.4938, "aspen_parkland")

    def test_red_deer_is_aspen_parkland(self):
        self.assertEco(52.2681, -113.8112, "aspen_parkland")

    def test_fort_mcmurray_is_boreal_mixedwood(self):
        self.assertEco(56.7264, -111.3803, "boreal_mixedwood")

    def test_grande_prairie_is_boreal_mixedwood(self):
        self.assertEco(55.1707, -118.7947, "boreal_mixedwood")

    def test_lethbridge_is_mixedgrass_prairie(self):
        self.assertEco(49.6956, -112.8451, "mixedgrass_prairie")

    def test_medicine_hat_is_mixedgrass_prairie(self):
        self.assertEco(50.0405, -110.6764, "mixedgrass_prairie")

    def test_calgary_is_fescue_foothills(self):
        """Calgary at -114.07°W sits in the fescue band (-114.5 to -113.5)
        of the starter polygon set. Real CEC data may place Calgary
        in transition; that's a per-polygon revision, not a code change."""
        self.assertEco(51.0447, -114.0719, "fescue_foothills")

    def test_banff_is_subalpine_montane(self):
        self.assertEco(51.1784, -115.5708, "subalpine_montane")

    def test_jasper_is_subalpine_montane(self):
        self.assertEco(52.8737, -118.0814, "subalpine_montane")


class TestOutsideAlberta(unittest.TestCase):
    """Points outside the shipped polygon coverage return None — never
    raise."""

    def test_vancouver_outside(self):
        self.assertIsNone(lookup_ecoregion(49.2827, -123.1207))

    def test_winnipeg_outside(self):
        self.assertIsNone(lookup_ecoregion(49.8951, -97.1384))

    def test_arctic_outside(self):
        self.assertIsNone(lookup_ecoregion(75.0, -100.0))

    def test_none_inputs_safe(self):
        self.assertIsNone(lookup_ecoregion(None, None))
        self.assertIsNone(lookup_ecoregion(53.5, None))
        self.assertIsNone(lookup_ecoregion(None, -113.5))


class TestLabelForKey(unittest.TestCase):

    def test_known_key(self):
        self.assertIn("Aspen Parkland", label_for_key("aspen_parkland"))

    def test_unknown_key_returns_key_itself(self):
        self.assertEqual(label_for_key("not_real"), "not_real")

    def test_none_returns_dash(self):
        self.assertEqual(label_for_key(None), "—")


if __name__ == "__main__":
    unittest.main()
