"""
tests/test_offline_communities.py

D2 — the offline (no-LLM) Generate Design path now seeds a couple of
site/goal-appropriate plant communities instead of a single default.
``_select_offline_communities`` is pure (fake community dicts, no DB), so
these tests are fast.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_design import _select_offline_communities  # noqa: E402

# Fake seeded-community catalogue (only the fields the selector reads).
_COMMS = [
    {"id": 1, "name": "Apple Tree Community", "description": "fruit guild"},
    {"id": 2, "name": "Prairie Pollinator Garden", "description": "nectar forbs"},
    {"id": 3, "name": "Continuous Bloom Pollinator Strip", "description": ""},
    {"id": 4, "name": "Aspen Parkland Edge", "description": "parkland transition"},
    {"id": 5, "name": "Riparian Willow Thicket", "description": "wet edge willows"},
    {"id": 6, "name": "Native Berry Hedge", "description": "berry shrubs"},
]


class TestSelectOfflineCommunities(unittest.TestCase):
    def test_goal_match_picks_pollinator_communities(self):
        ids = _select_offline_communities(_COMMS, ["pollinator"], None, None)
        # the two pollinator-named communities score, the apple guild doesn't
        self.assertIn(2, ids)
        self.assertIn(3, ids)
        self.assertNotIn(1, ids)

    def test_picks_up_to_max_n(self):
        ids = _select_offline_communities(
            _COMMS, ["pollinator", "food_producing", "year_round_interest"],
            None, None, max_n=2)
        self.assertLessEqual(len(ids), 2)

    def test_ecoregion_boosts_matching_community(self):
        # An aspen-parkland site should surface the parkland community first
        # even without a goal that names it.
        ids = _select_offline_communities(
            _COMMS, [], {"ecoregion_key": "aspen_parkland"}, None)
        self.assertEqual(ids[0], 4)

    def test_riparian_ecoregion(self):
        ids = _select_offline_communities(
            _COMMS, [], {"ecoregion_key": "riparian"}, None)
        self.assertIn(5, ids)

    def test_default_when_nothing_scores_no_budget(self):
        ids = _select_offline_communities(_COMMS, [], None, None)
        self.assertEqual(ids, [1])      # first catalogue entry as a sensible default

    def test_no_default_under_budget(self):
        # Budget mode must not force an arbitrary community when none fit the goals.
        ids = _select_offline_communities(_COMMS, [], None, budget=200.0)
        self.assertEqual(ids, [])

    def test_empty_catalogue(self):
        self.assertEqual(_select_offline_communities([], ["pollinator"], None, None), [])


if __name__ == "__main__":
    unittest.main()
