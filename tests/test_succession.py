"""
tests/test_succession.py

N5 — the pure ecological-succession helpers behind the growth timeline:
restoration-stage labels, successional-role detection, the fade in/out
presence factor, and the dynamic time-horizon clamp. All Qt-free / DB-free
(get_plant is injected), so no temp DB is needed here.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.succession import (  # noqa: E402
    restoration_stage, year_label, successional_role, presence_factor,
    timeline_max_years, years_to_maturity,
    TIMELINE_FLOOR_YEARS, TIMELINE_CAP_YEARS,
)


class TestStages(unittest.TestCase):
    def test_stage_progression(self):
        self.assertEqual(restoration_stage(0), "Planting")
        self.assertEqual(restoration_stage(1), "Pioneer forbs")
        self.assertEqual(restoration_stage(3), "Forb–grass matrix")
        self.assertEqual(restoration_stage(5), "Shrubs establishing")
        self.assertEqual(restoration_stage(10), "Climax / canopy")
        self.assertEqual(restoration_stage(45), "Climax / canopy")

    def test_year_label(self):
        self.assertEqual(year_label(0), "Year 0 (Planting)")
        self.assertIn("Year 3", year_label(3))
        self.assertIn("Forb–grass", year_label(3))


class TestRole(unittest.TestCase):
    def test_pioneer_from_tag(self):
        self.assertEqual(
            successional_role({"permaculture_uses": "nitrogen_fixer,early_successional"}),
            "pioneer")

    def test_climax_from_tag(self):
        self.assertEqual(
            successional_role({"permaculture_uses": "climax,wildlife"}), "climax")

    def test_climax_heuristic_for_long_lived_tree(self):
        # untagged long-lived tree reads as climax
        self.assertEqual(
            successional_role({"plant_type": "tree", "years_to_maturity": 30}),
            "climax")

    def test_fast_tree_not_forced_climax(self):
        # a quick-maturing tree is not auto-climax
        self.assertEqual(
            successional_role({"plant_type": "tree", "years_to_maturity": 8}),
            "mid")

    def test_plain_herb_is_mid(self):
        self.assertEqual(successional_role({"plant_type": "herb"}), "mid")

    def test_pioneer_tag_beats_heuristic(self):
        # an early-successional tree is a pioneer even if long-lived
        self.assertEqual(
            successional_role({"plant_type": "tree", "years_to_maturity": 40,
                               "permaculture_uses": "early_successional"}),
            "pioneer")


class TestPresence(unittest.TestCase):
    def test_year_zero_full(self):
        for role in ("pioneer", "climax", "mid"):
            self.assertEqual(presence_factor(role, 0, 15), 1.0)

    def test_pioneer_forb_fades_out(self):
        # short-lived forb (ytm 2): full while establishing, remnant later
        self.assertEqual(presence_factor("pioneer", 2, 2), 1.0)     # early: full
        self.assertEqual(presence_factor("pioneer", 20, 2), 0.2)    # late: remnant
        mid = presence_factor("pioneer", 6, 2)
        self.assertTrue(0.2 < mid < 1.0)                            # mid: ramping

    def test_pioneer_tree_persists_within_horizon(self):
        # a long-lived pioneer tree (lodgepole, ytm 60) does NOT fade out at
        # full canopy within the design horizon — the fade scales to lifecycle
        self.assertEqual(presence_factor("pioneer", 60, 60), 1.0)

    def test_climax_fades_in(self):
        early = presence_factor("climax", 1, 30)
        late = presence_factor("climax", 30, 30)
        self.assertLess(early, late)
        self.assertEqual(late, 1.0)
        self.assertGreaterEqual(early, 0.2)                         # never invisible

    def test_mid_constant(self):
        self.assertEqual(presence_factor("mid", 5, 5), 1.0)


class TestHorizon(unittest.TestCase):
    _FAKE = {
        1: {"plant_type": "tree", "years_to_maturity": 35},
        2: {"plant_type": "herb", "years_to_maturity": 2},
        3: {"plant_type": "shrub"},   # no ytm → type default (5)
    }

    def _get(self, pid):
        return self._FAKE.get(pid)

    def test_extends_to_slowest_tree(self):
        plants = [{"plant_id": 1}, {"plant_id": 2}]
        self.assertEqual(timeline_max_years(plants, get_plant=self._get), 35)

    def test_floor_when_only_fast_plants(self):
        plants = [{"plant_id": 2}, {"plant_id": 3}]
        self.assertEqual(timeline_max_years(plants, get_plant=self._get),
                         TIMELINE_FLOOR_YEARS)

    def test_cap_is_respected(self):
        self._FAKE[9] = {"plant_type": "tree", "years_to_maturity": 200}
        self.assertEqual(
            timeline_max_years([{"plant_id": 9}], get_plant=self._get),
            TIMELINE_CAP_YEARS)

    def test_empty_design_is_floor(self):
        self.assertEqual(timeline_max_years([], get_plant=self._get),
                         TIMELINE_FLOOR_YEARS)

    def test_years_to_maturity_default(self):
        self.assertEqual(years_to_maturity({"plant_type": "tree"}), 15)
        self.assertEqual(years_to_maturity({"years_to_maturity": 7}), 7)


if __name__ == "__main__":
    unittest.main()
