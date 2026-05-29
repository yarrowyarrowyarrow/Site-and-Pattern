"""
tests/test_design_goals.py

Unit tests for the design-goal registry (src.design_goals). Pure and headless
— no database, no Qt, no network.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.design_goals as dg  # noqa: E402


class TestDesignGoals(unittest.TestCase):

    def test_goal_keys_unique_and_nonempty(self):
        keys = dg.goal_keys()
        self.assertTrue(keys)
        self.assertEqual(len(keys), len(set(keys)))

    def test_get_goal_known_and_unknown(self):
        self.assertIsNotNone(dg.get_goal("native_only"))
        self.assertIsNone(dg.get_goal("not_a_goal"))

    def test_filters_merge_for_backed_goals(self):
        merged = dg.filters_for_goals(["food_producing", "native_only"])
        self.assertEqual(merged, {"edible_only": True, "native_only": True})

    def test_filters_skip_unknown_and_unbacked(self):
        # pet_friendly is hint-only (no filters); the bogus key is ignored.
        merged = dg.filters_for_goals(["pet_friendly", "bogus", "pollinator"])
        self.assertEqual(merged, {"pollinator_only": True})

    def test_filters_none_is_empty(self):
        self.assertEqual(dg.filters_for_goals(None), {})

    def test_hints_present_for_backed_and_unbacked(self):
        hints = dg.hints_for_goals(["native_only", "pet_friendly"])
        self.assertEqual(len(hints), 2)
        self.assertTrue(any("toxic" in h.lower() for h in hints))

    def test_hints_deduplicated(self):
        self.assertEqual(len(dg.hints_for_goals(["pet_friendly", "pet_friendly"])), 1)

    def test_community_hints(self):
        self.assertIn("Berry", dg.community_name_hints(["food_producing"]))

    def test_unbacked_goals(self):
        unbacked = dg.unbacked_goals([
            "native_only", "pollinator", "food_producing",
            "flowers_all_season", "pet_friendly", "kid_friendly",
            "year_round_interest",
        ])
        self.assertEqual(
            set(unbacked),
            {"flowers_all_season", "pet_friendly", "kid_friendly",
             "year_round_interest"},
        )

    def test_backed_goals_have_filters(self):
        for g in dg.GOALS:
            if g.backed:
                self.assertTrue(
                    g.filters, f"backed goal {g.key} should declare filters")


if __name__ == "__main__":
    unittest.main()
