"""
tests/test_planting_spacing.py — layer/type-aware, spread-aware spacing (F22/F35).

Pure geometry / arithmetic; no Qt or DB.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.planting_spacing as ps  # noqa: E402

# A ~30 m square near Edmonton, GeoJSON [lng, lat] ring (matches test_area_fill).
_LAT = 53.5
_DLAT = 30.0 / 111_320.0
_DLNG = 30.0 / (111_320.0 * 0.5948)
_RING = [
    [-113.50, _LAT],
    [-113.50 + _DLNG, _LAT],
    [-113.50 + _DLNG, _LAT + _DLAT],
    [-113.50, _LAT + _DLAT],
]


class TestPlantSpacing(unittest.TestCase):
    def test_type_ordering(self):
        base = 0.5
        tree = ps.plant_spacing({"plant_type": "tree"}, base)
        shrub = ps.plant_spacing({"plant_type": "shrub"}, base)
        per = ps.plant_spacing({"plant_type": "herb"}, base)
        ground = ps.plant_spacing({"plant_type": "groundcover"}, base)
        self.assertGreater(tree, shrub)
        self.assertGreater(shrub, per)
        self.assertGreater(per, ground)

    def test_spread_widens(self):
        base = 0.5
        clump = ps.plant_spacing(
            {"plant_type": "herb", "spread_habit": "clumping"}, base)
        spread = ps.plant_spacing(
            {"plant_type": "herb", "spread_habit": "aggressive_rhizomatous"}, base)
        self.assertGreater(spread, clump)

    def test_canopy_floor(self):
        # A big mature canopy floors the spacing above the base×factor value.
        s = ps.plant_spacing({"plant_type": "shrub", "mature_canopy_m": 9.0}, 0.5)
        self.assertGreaterEqual(s, 9.0)

    def test_layer_buckets(self):
        self.assertEqual(ps.layer_of("tree"), "canopy")
        self.assertEqual(ps.layer_of("groundcover"), "ground")
        self.assertEqual(ps.bucket_for_member({"layer": "overstory"}), "canopy")
        self.assertEqual(ps.bucket_for_member({"layer": "groundcover"}), "ground")
        # Falls back to plant_type when no vegetation layer is set.
        self.assertEqual(ps.bucket_for_member({"plant_type": "shrub"}), "shrub")


class TestArrangeConcentric(unittest.TestCase):
    def _members(self):
        return [
            {"plant_id": 1, "layer": "overstory", "spacing_m": 4.0},
            {"plant_id": 2, "layer": "shrub_layer", "spacing_m": 1.5},
            {"plant_id": 3, "layer": "shrub_layer", "spacing_m": 1.5},
            {"plant_id": 4, "layer": "herbaceous", "spacing_m": 0.5},
            {"plant_id": 5, "layer": "herbaceous", "spacing_m": 0.5},
            {"plant_id": 6, "layer": "groundcover", "spacing_m": 0.3},
        ]

    def test_all_members_placed_with_offsets(self):
        arranged, radius = ps.arrange_concentric(self._members())
        self.assertEqual(len(arranged), 6)
        self.assertGreater(radius, 0.0)
        for m in arranged:
            self.assertIn("offset_x", m)
            self.assertIn("offset_y", m)

    def test_single_tree_centred(self):
        arranged, _ = ps.arrange_concentric(
            [{"plant_id": 1, "layer": "overstory", "spacing_m": 4.0}])
        self.assertEqual((arranged[0]["offset_x"], arranged[0]["offset_y"]), (0.0, 0.0))

    def test_layers_radiate_outward(self):
        arranged, _ = ps.arrange_concentric(self._members())
        by_id = {m["plant_id"]: m for m in arranged}

        def dist(pid):
            m = by_id[pid]
            return math.hypot(m["offset_x"], m["offset_y"])
        # tree at centre; groundcover further out than the shrubs.
        self.assertAlmostEqual(dist(1), 0.0, places=6)
        self.assertGreater(dist(6), dist(2))

    def test_max_radius_caps_the_arrangement(self):
        # Without a cap the arrangement reaches some natural radius; capping it
        # tighter must pull every member inside the cap and report that radius.
        _arranged, natural = ps.arrange_concentric(self._members())
        cap = max(0.5, natural / 2.0)
        arranged, radius = ps.arrange_concentric(self._members(), max_radius_m=cap)
        self.assertLessEqual(radius, cap + 1e-6)
        for m in arranged:
            self.assertLessEqual(
                math.hypot(m["offset_x"], m["offset_y"]), cap + 0.05)

    def test_max_radius_leaves_small_arrangements_alone(self):
        # A generous cap above the natural radius changes nothing.
        base, _ = ps.arrange_concentric(self._members())
        capped, _ = ps.arrange_concentric(self._members(), max_radius_m=1000.0)
        self.assertEqual([(m["offset_x"], m["offset_y"]) for m in base],
                         [(m["offset_x"], m["offset_y"]) for m in capped])


class TestLayeredFill(unittest.TestCase):
    def test_groundcover_denser_than_trees(self):
        from collections import Counter
        typed = [
            {"plant_id": 1, "plant_type": "tree", "weight": 1.0},
            {"plant_id": 2, "plant_type": "groundcover", "weight": 1.0},
        ]
        recs = ps.layered_fill_plan(_RING, typed, base_m=0.6)
        self.assertGreater(len(recs), 0)
        c = Counter(pid for pid, _, _ in recs)
        self.assertIn(2, c)                       # groundcover present
        self.assertGreater(c[2], c.get(1, 0))     # far more groundcover than trees

    def test_empty_inputs(self):
        self.assertEqual(ps.layered_fill_plan([], [{"plant_id": 1,
                                                    "plant_type": "tree"}], 1.0), [])
        self.assertEqual(ps.layered_fill_plan(_RING, [], 1.0), [])


if __name__ == "__main__":
    unittest.main()
