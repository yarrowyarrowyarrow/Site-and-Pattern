"""
tests/test_ecoregion.py

Verifies the V1.36 ecoregion auto-detect via point-in-polygon against
the shipped ``data/ecoregions_canada.geojson``. Each test asserts a
real city's lat/lng resolves to the canonical ecoregion key the plant
filter expects.

The shipped starter polygon set is a rectangular partition of the
prairie provinces — Alberta west of the -110 meridian, Saskatchewan
east of it (V2.14) — and the city assertions below are calibrated
against that starter set. When a future revision replaces those
rectangles with real CEC polygons (via ``scripts/prepare_ecoregions.py``),
expect some of these assertions to need adjustment for boundary cases
like Calgary (which sits at the prairie-foothills transition).
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
            "aspen_parkland", "mixedgrass_prairie", "moist_mixedgrass",
            "fescue_foothills", "boreal_mixedwood", "riparian", "wet_meadow",
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


class TestSaskatchewanCityLookups(unittest.TestCase):
    """SK city coordinates → expected ecoregion key (V2.14 expansion).
    SK polygons lie east of the -110 meridian (the AB/SK border)."""

    def assertEco(self, lat: float, lng: float, expected_key: str):
        got = lookup_ecoregion(lat, lng)
        self.assertEqual(got, expected_key,
                         f"({lat}, {lng}) → got {got!r}, expected {expected_key!r}")

    def test_regina_is_moist_mixedgrass(self):
        self.assertEco(50.4452, -104.6189, "moist_mixedgrass")

    def test_lumsden_is_moist_mixedgrass(self):
        self.assertEco(50.6500, -104.8700, "moist_mixedgrass")

    def test_saskatoon_is_moist_mixedgrass(self):
        self.assertEco(52.1332, -106.6700, "moist_mixedgrass")

    def test_north_battleford_is_aspen_parkland(self):
        self.assertEco(52.7575, -108.2861, "aspen_parkland")

    def test_battleford_is_aspen_parkland(self):
        self.assertEco(52.7368, -108.2967, "aspen_parkland")

    def test_swift_current_is_mixedgrass_prairie(self):
        self.assertEco(50.2881, -107.7939, "mixedgrass_prairie")


class TestOutsideCoverage(unittest.TestCase):
    """Points outside the shipped AB+SK polygon coverage return None — never
    raise. Winnipeg (east of the SK/MB border) and Vancouver stay uncovered."""

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


# ═══════════════════════════════════════════════════════════════════════════
#  V2.38 — two axes, and a site that is in more than one region
# ═══════════════════════════════════════════════════════════════════════════
#
# User feedback: "I'd prefer it breakdown into the individual ecoregions it
# exists in so when I add BC and other areas of turtle island we simply add
# more ecoregions." That only works if the vocabulary IS the polygon file, so
# adding a region is adding a polygon — which is what these hold down.

from src import ecoregion as _eco  # noqa: E402


class TestTheVocabularyIsTheFile(unittest.TestCase):
    """The geographic vocabulary is read from the shipped polygons, not from a
    list beside them that has to be remembered."""

    def test_every_polygon_key_is_offered_in_the_filter(self):
        from_file = {(f.get("properties") or {}).get("key")
                     for f in _load_features()}
        from_file.discard(None)
        self.assertTrue(from_file)
        self.assertTrue(from_file.issubset(set(_eco.geographic_keys())),
                        "a shipped polygon exists that no dropdown offers")

    def test_the_two_axes_are_separate(self):
        """Geographic regions are places; moisture niches are conditions that
        occur inside any of them. Mixing them is what made 'which ecoregion is
        my site in?' and 'is this spot wet?' one control."""
        geo = set(_eco.geographic_keys())
        wet = {k for k, _n, _w in _eco.MOISTURE_NICHES}
        self.assertEqual(geo & wet, set())
        self.assertEqual(set(_eco.ecoregion_keys()), geo | wet)
        for k in wet:
            self.assertTrue(_eco.is_moisture_niche(k))
        for k in geo:
            self.assertFalse(_eco.is_moisture_niche(k))

    def test_no_lookup_can_return_a_moisture_niche(self):
        """No lat/lng puts you in 'wet ground'. If a polygon ever claimed one,
        the site panel would assert a moisture condition from a map."""
        for f in _load_features():
            key = (f.get("properties") or {}).get("key")
            self.assertFalse(_eco.is_moisture_niche(key),
                             f"{key} is a condition, not a place")

    def test_name_and_place_stay_apart(self):
        """Packed into one label they elided mid-word in the dropdown."""
        for key, name, where in _eco.ecoregions():
            self.assertTrue(name, key)
            self.assertNotIn("(", name, f"{key}: place packed into the name")

    def test_the_fallback_matches_the_shipped_file(self):
        """The hard-coded list is only for a build whose resources are broken.
        If it drifts from the file, that build silently offers a different
        vocabulary than the one the polygons use."""
        self.assertEqual([k for k, _n, _w in _eco._FALLBACK_GEOGRAPHIC],
                         list(_eco.geographic_keys()))
        self.assertEqual(_eco._FALLBACK_GEOGRAPHIC,
                         list(_eco.geographic_ecoregions()))

    def test_display_order_is_stable_and_deduplicated(self):
        keys = _eco.geographic_keys()
        self.assertEqual(len(keys), len(set(keys)),
                         "a region drawn as two lobes was offered twice")

    def test_a_packed_legacy_label_still_splits(self):
        self.assertEqual(_eco._split_label("Aspen Parkland (central AB)"),
                         ("Aspen Parkland", "central AB"))
        self.assertEqual(_eco._split_label("Riparian"), ("Riparian", ""))
        # The last bracket wins, so a name with its own brackets survives.
        self.assertEqual(_eco._split_label("Boreal (mixedwood) Plain (north)"),
                         ("Boreal (mixedwood) Plain", "north"))


class TestASiteCanBeInTwo(unittest.TestCase):
    """``lookup_ecoregion`` returned the first match and stopped. A property
    near a boundary belongs to both, and the second one is exactly the species
    list that was going missing."""

    def test_the_foothills_overlap_reports_both(self):
        # The shipped aspen_parkland and subalpine_montane rectangles overlap
        # in lng[-115, -114.5] x lat[52, 54] — the Rocky Mountain House /
        # Nordegg transition, where parkland really does run into montane.
        keys = _eco.lookup_ecoregions(53.0, -114.8)
        self.assertIn("aspen_parkland", keys)
        self.assertIn("subalpine_montane", keys)

    def test_the_singular_shim_still_answers_one(self):
        self.assertEqual(_eco.lookup_ecoregion(53.0, -114.8),
                         _eco.lookup_ecoregions(53.0, -114.8)[0])

    def test_an_ordinary_site_reports_exactly_one(self):
        self.assertEqual(_eco.lookup_ecoregions(53.55, -113.49),
                         ["aspen_parkland"])          # Edmonton

    def test_two_lobes_of_one_region_count_once(self):
        """moist_mixedgrass ships as two rectangles. Being in one of them is
        being in the region once, not twice."""
        keys = _eco.lookup_ecoregions(52.13, -106.67)  # Saskatoon
        self.assertEqual(keys, ["moist_mixedgrass"])

    def test_outside_everything_is_empty_not_a_guess(self):
        self.assertEqual(_eco.lookup_ecoregions(49.28, -123.12), [])   # Vancouver
        self.assertEqual(_eco.lookup_ecoregions(None, None), [])

    def test_the_detection_payload_carries_every_match(self):
        from src.property_data import fetch_ecoregion
        data = fetch_ecoregion(53.0, -114.8)
        self.assertEqual(data["keys"], _eco.lookup_ecoregions(53.0, -114.8))
        self.assertEqual(data["key"], data["keys"][0])
        # The readout names both, so the user can see why two are checked.
        self.assertIn("Aspen Parkland", data["label"])
        self.assertIn("Subalpine", data["label"])

    def test_no_pin_no_payload(self):
        from src.property_data import fetch_ecoregion
        self.assertIsNone(fetch_ecoregion(49.28, -123.12))


class TestOneVocabularyEverywhere(unittest.TestCase):
    """Every list of ecoregions in the app must be the same list.

    Before V2.38 there were four hand-kept copies — the plant filter, the data
    validator, the community-library habitat labels, and the polygon file — and
    a key missing from one of them did not fail. It went quiet: an ecoregion
    with no label silently read "Generalist", which is how `moist_mixedgrass`,
    the commonest tag in the catalogue at 246 plants, went unlabelled for two
    minor versions.
    """

    def test_the_validator_accepts_exactly_the_vocabulary(self):
        from src.data_quality import _load_ecoregion_keys
        self.assertEqual(_load_ecoregion_keys(), set(_eco.ecoregion_keys()))

    def test_the_validator_refuses_an_empty_vocabulary(self):
        """A silent pass is worse than a loud failure in a data gate: an empty
        key set makes every ecoregion token in the catalogue valid."""
        import src.ecoregion as mod
        from src.data_quality import _load_ecoregion_keys
        original = mod.ecoregion_keys
        mod.ecoregion_keys = lambda: []
        try:
            with self.assertRaises(RuntimeError):
                _load_ecoregion_keys()
        finally:
            mod.ecoregion_keys = original

    def test_the_community_habitat_labels_cover_the_vocabulary(self):
        from src.db import polycultures
        self.assertEqual(set(polycultures.ECOREGION_LABELS),
                         set(_eco.ecoregion_keys()))
        for key, name, _where in _eco.ecoregions():
            self.assertEqual(polycultures.ECOREGION_LABELS[key], name)

    def test_the_plant_filter_offers_the_vocabulary(self):
        """AST-only — plant_panel imports PyQt6, and this must hold on a bare
        container too."""
        import ast
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "plant_panel.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported = any(
            isinstance(n, ast.ImportFrom)
            and n.module == "src.ecoregion"
            and any(a.name == "ECOREGIONS" for a in n.names)
            for n in ast.walk(tree))
        self.assertTrue(imported,
                        "plant_panel no longer builds its choices from the "
                        "shared vocabulary — that is a second list to keep")

    def test_every_key_appears_in_the_habitat_facet_choices(self):
        from src.db import polycultures
        choices = polycultures.facet_filter_choices()["habitat"]
        for _key, name, _where in _eco.ecoregions():
            self.assertIn(name, choices)
