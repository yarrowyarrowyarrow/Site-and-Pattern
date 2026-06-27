"""
tests/test_plant_conditions.py — multi-value sun/water + rarity filter (V1.84).

Covers:
  * condition_tokens / condition_matches (pure helpers)
  * placement_score best-fit (max over a plant's tolerances) + shade-tag any-of
  * zoning with comma-delimited values
  * search_plants: sun_req / water_needs match multi-value rows; the
    availability_in allowlist partitions the catalogue by sourcing tier

DB tests use the temp-DB pattern (never the real user DB); no Qt.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod  # noqa: E402

_TMP = tempfile.mkdtemp(prefix="permadesign_conditions_test_")
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "t.db")

from src.db.plants import init_db, search_plants  # noqa: E402
from src.plant_conditions import condition_tokens, condition_matches  # noqa: E402
import src.placement_score as ps  # noqa: E402
import src.zoning as zoning  # noqa: E402


class TestConditionHelpers(unittest.TestCase):
    def test_tokens(self):
        self.assertEqual(condition_tokens("full_sun"), ["full_sun"])
        self.assertEqual(condition_tokens("full_sun,partial_shade"),
                         ["full_sun", "partial_shade"])
        self.assertEqual(condition_tokens(" Full_Sun , Partial_Shade "),
                         ["full_sun", "partial_shade"])
        self.assertEqual(condition_tokens(None), [])
        self.assertEqual(condition_tokens(""), [])
        self.assertEqual(condition_tokens(["low", "medium"]), ["low", "medium"])

    def test_matches(self):
        self.assertTrue(condition_matches("full_sun,partial_shade", "partial_shade"))
        self.assertTrue(condition_matches("full_sun", "full_sun"))
        self.assertFalse(condition_matches("full_sun", "full_shade"))
        # empty target = no restriction
        self.assertTrue(condition_matches("full_sun", ""))


class TestPlacementMultiValue(unittest.TestCase):
    def _cell(self, shade):
        return ps.CellEnv(shade_fraction=shade, elevation_pct=0.5,
                          aspect_deg=180.0, slope_pct=5.0, is_edge=False)

    def test_best_fit_beats_single(self):
        # On a partly-shaded cell, full_sun alone scores poorly; adding
        # partial_shade (which fits) must not lower the score (best-fit max).
        cell = self._cell(0.4)
        only_sun = ps.score_cell_for_plant(
            {"sun_requirement": "full_sun", "water_needs": "low",
             "plant_type": "herb"}, cell)
        both = ps.score_cell_for_plant(
            {"sun_requirement": "full_sun,partial_shade", "water_needs": "low",
             "plant_type": "herb"}, cell)
        self.assertGreater(both, only_sun)

    def test_shade_tag_any_of(self):
        self.assertTrue(ps.shade_tag_matches_plant("full_sun,full_shade", "full_shade"))
        self.assertTrue(ps.shade_tag_matches_plant("full_sun,full_shade", "full_sun"))
        # single value still works
        self.assertFalse(ps.shade_tag_matches_plant("full_sun", "full_shade"))


class TestZoningMultiValue(unittest.TestCase):
    def test_shaded_via_token(self):
        z = zoning.preferred_zone_for_plant(
            {"sun_requirement": "full_sun,partial_shade", "water_needs": "low,medium"})
        self.assertEqual(z, zoning.SHADED)

    def test_wet_via_high_token(self):
        z = zoning.preferred_zone_for_plant(
            {"sun_requirement": "full_sun", "water_needs": "medium,high"})
        self.assertEqual(z, zoning.WET)

    def test_dry_via_low_only(self):
        z = zoning.preferred_zone_for_plant(
            {"sun_requirement": "full_sun", "water_needs": "low"})
        self.assertEqual(z, zoning.DRY)


class TestSearchMultiValueAndRarity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_sun_filter_matches_multivalue_rows(self):
        rows = search_plants(sun_req="partial_shade")
        self.assertTrue(rows)
        # every result tolerates partial_shade
        for r in rows:
            self.assertIn("partial_shade", condition_tokens(r["sun_requirement"]))
        # and at least one of them is a genuine multi-value row
        self.assertTrue(any("," in (r["sun_requirement"] or "") for r in rows),
                        "expected some comma-delimited sun values after curation")

    def test_water_filter_matches_multivalue_rows(self):
        rows = search_plants(water_needs="medium")
        self.assertTrue(rows)
        for r in rows:
            self.assertIn("medium", condition_tokens(r["water_needs"]))

    def test_availability_in_partitions(self):
        everything = search_plants()
        big = search_plants(availability_in=["big_box"])
        common = search_plants(availability_in=["big_box", "garden_centre"])
        self.assertTrue(big)
        # big_box ⊆ (big_box + garden_centre) ⊂ everything
        self.assertLess(len(big), len(common))
        self.assertLess(len(common), len(everything))
        for r in big:
            self.assertEqual(r["availability_class"], "big_box")
        for r in common:
            self.assertIn(r["availability_class"], ("big_box", "garden_centre"))

    def test_availability_empty_is_no_restriction(self):
        self.assertEqual(len(search_plants(availability_in=[])),
                         len(search_plants()))


class TestMultiSelectFilters(unittest.TestCase):
    """V1.85: facet dropdowns pass lists; ANY within type/sun, ALL within use."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_plant_type_list_is_any_of(self):
        ts = search_plants(plant_type=["tree", "shrub"])
        self.assertTrue(ts)
        self.assertTrue(all(p["plant_type"] in ("tree", "shrub") for p in ts))
        kinds = {p["plant_type"] for p in ts}
        self.assertEqual(kinds, {"tree", "shrub"})  # both present
        # union equals the two single-type queries combined
        self.assertEqual(
            len(ts),
            len(search_plants(plant_type="tree")) + len(search_plants(plant_type="shrub")))

    def test_sun_list_is_any_of(self):
        rows = search_plants(sun_req=["full_sun", "full_shade"])
        self.assertTrue(rows)
        for r in rows:
            toks = condition_tokens(r["sun_requirement"])
            self.assertTrue("full_sun" in toks or "full_shade" in toks)

    def test_perm_use_list_is_all_of(self):
        poll = search_plants(perm_use="pollinator")
        both = search_plants(perm_use=["pollinator", "host_plant"])
        self.assertTrue(both)
        self.assertLessEqual(len(both), len(poll))   # AND narrows
        both_ids = {p["id"] for p in both}
        self.assertTrue(both_ids <= {p["id"] for p in poll})  # subset

    def test_string_backward_compat(self):
        # A bare string still behaves as a single-value filter.
        self.assertEqual(len(search_plants(plant_type="tree")),
                         len(search_plants(plant_type=["tree"])))

    def test_empty_list_no_restriction(self):
        everything = len(search_plants())
        self.assertEqual(everything, len(search_plants(plant_type=[], sun_req=[],
                                                       water_needs=[], perm_use=[])))


if __name__ == "__main__":
    unittest.main()
