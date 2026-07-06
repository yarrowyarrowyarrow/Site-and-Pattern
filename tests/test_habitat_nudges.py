"""
tests/test_habitat_nudges.py

The "what would help most" nudges (V2.13): habitat_score.habitat_nudges turns
a HabitatScore into ranked, ranged, actionable suggestions. Qt-free — builds
HabitatScore instances directly rather than driving the DB.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.habitat_score import HabitatScore, habitat_nudges, _gap_phrase


def _score(**over):
    base = dict(
        total=0, grade="", n_species=0, n_total_plants=0, scored_plant_ids=[],
        native_species=0, native_ratio=0.0, score_native=0.0,
        keystone_species=[], score_keystone=0.0,
        host_species=[], score_host=0.0,
        bird_species=[], score_bird=0.0,
        layers_present=[], score_layers=0.0,
        habitat_struct_types=[], score_structs=0.0,
        bloom_months=[], gap_months=[], score_bloom=0.0,
        n_lepidoptera_supported=0,
    )
    base.update(over)
    return HabitatScore(**base)


class TestGapPhrase(unittest.TestCase):

    def test_single(self):
        self.assertEqual(_gap_phrase([5]), "May")

    def test_two(self):
        self.assertEqual(_gap_phrase([5, 6]), "May & Jun")

    def test_three(self):
        self.assertEqual(_gap_phrase([5, 6, 7]), "May, Jun & Jul")

    def test_empty(self):
        self.assertEqual(_gap_phrase([]), "")


class TestHabitatNudges(unittest.TestCase):

    def test_none_score_no_nudges(self):
        self.assertEqual(habitat_nudges(None), [])

    def test_full_score_no_nudges(self):
        # Everything maxed → nothing to suggest.
        sc = _score(
            n_species=10, native_species=10, score_native=20.0,
            keystone_species=["a", "b", "c", "d", "e"], score_keystone=15.0,
            host_species=list("abcdefghij"), score_host=10.0,
            bird_species=list("abcdefghij"), score_bird=10.0,
            layers_present=["overstory", "shrub", "herbaceous",
                            "groundcover", "vine"], score_layers=15.0,
            habitat_struct_types=["pond", "swale", "snag", "bee_hotel",
                                  "brush_pile"], score_structs=10.0,
            bloom_months=list(range(4, 11)), gap_months=[], score_bloom=20.0,
        )
        self.assertEqual(habitat_nudges(sc), [])

    def test_ranked_by_headroom_and_limited(self):
        # Bloom gap (20 headroom) should outrank a near-full structure line.
        sc = _score(
            n_species=4, native_species=4, score_native=20.0,
            keystone_species=[], score_keystone=0.0,
            host_species=[], score_host=0.0,
            gap_months=[5, 6], score_bloom=0.0,
        )
        nudges = habitat_nudges(sc, limit=2)
        self.assertEqual(len(nudges), 2)
        # Descending headroom.
        self.assertGreaterEqual(nudges[0]["headroom"], nudges[1]["headroom"])
        # Bloom is the biggest lever here (20 pts).
        self.assertIn("bloom", nudges[0]["text"].lower())

    def test_bloom_gap_names_the_months(self):
        sc = _score(gap_months=[7], score_bloom=17.14)
        nudges = habitat_nudges(sc, limit=8)
        self.assertTrue(any("Jul" in n["text"] for n in nudges))

    def test_native_nudge_mentions_swap(self):
        sc = _score(n_species=10, native_species=6, score_native=12.0)
        nudges = habitat_nudges(sc, limit=8)   # want every applicable nudge
        native = [n for n in nudges if "aren't Alberta-native" in n["text"]]
        self.assertTrue(native)
        self.assertIn("4 of 10", native[0]["text"])

    def test_no_nonnatives_no_native_nudge(self):
        # All native → the native line must not appear even though other gaps do.
        sc = _score(n_species=5, native_species=5, score_native=20.0,
                    gap_months=[5], score_bloom=17.14)
        nudges = habitat_nudges(sc)
        self.assertFalse(any("aren't Alberta-native" in n["text"]
                             for n in nudges))

    def test_missing_layers_listed(self):
        sc = _score(layers_present=["herbaceous"], score_layers=3.0)
        nudges = habitat_nudges(sc, limit=8)
        layer = [n for n in nudges if "Missing layers" in n["text"]]
        self.assertTrue(layer)
        self.assertIn("overstory", layer[0]["text"])

    def test_headroom_values_are_positive(self):
        sc = _score(n_species=3, native_species=1, score_native=6.67,
                    gap_months=[5, 6, 7], score_bloom=11.43)
        for n in habitat_nudges(sc, limit=5):
            self.assertGreater(n["headroom"], 0.5)


if __name__ == "__main__":
    unittest.main()
