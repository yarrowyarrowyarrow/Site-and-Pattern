"""
tests/test_scene3d.py

D1 foundation — the shared placement/timeline state module. Pure (no Qt / DB;
get_plant injected). Guards that growth_scale_factor matches the 2D timeline's
formula and that per-plant 3D state scales height/canopy and carries the
succession presence opacity.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scene3d import (  # noqa: E402
    growth_scale_factor, spread_scale_factor, spread_aggressiveness,
    plant_3d_state, placed_plants_3d_state,
)


class TestGrowthScaleFactor(unittest.TestCase):
    def test_year_zero_and_maturity_are_full(self):
        self.assertEqual(growth_scale_factor(0, 20, "steady"), 1.0)
        self.assertEqual(growth_scale_factor(20, 20, "steady"), 1.0)
        self.assertEqual(growth_scale_factor(40, 20, "steady"), 1.0)

    def test_steady_is_linear(self):
        self.assertAlmostEqual(growth_scale_factor(10, 20, "steady"), 0.5)

    def test_fast_early_is_sqrt(self):
        self.assertAlmostEqual(growth_scale_factor(5, 20, "fast_early"),
                               math.sqrt(0.25))

    def test_slow_start_is_pow(self):
        self.assertAlmostEqual(growth_scale_factor(5, 20, "slow_start"),
                               0.25 ** 1.5)

    def test_floor_clamp(self):
        # very young → never below the 0.1 floor
        self.assertEqual(growth_scale_factor(1, 1000, "steady"), 0.1)

    def test_matches_2d_inline_formula(self):
        # Replicate the old inline 2D formula and confirm parity across cases.
        def inline(year, ytm, curve):
            if year == 0 or year >= ytm:
                f = 1.0
            else:
                r = year / ytm
                f = (math.sqrt(r) if curve == "fast_early"
                     else r ** 1.5 if curve == "slow_start" else r)
            return max(0.1, min(1.0, f))
        for ytm in (2, 5, 15, 60):
            for curve in ("steady", "fast_early", "slow_start"):
                for year in (0, 1, 3, 5, 10, 30, 60):
                    self.assertAlmostEqual(
                        growth_scale_factor(year, ytm, curve),
                        inline(year, ytm, curve), places=9,
                        msg=f"{year}/{ytm}/{curve}")


class TestSpreadScaleFactor(unittest.TestCase):
    def test_non_spreaders_never_expand(self):
        for habit in ("", "clumping", "unknown_value"):
            self.assertEqual(spread_scale_factor(10, habit, 20), 1.0)

    def test_year_zero_is_one(self):
        self.assertEqual(
            spread_scale_factor(0, "aggressive_rhizomatous", 20), 1.0)

    def test_spreaders_widen_over_time(self):
        early = spread_scale_factor(5, "aggressive_rhizomatous", 20)
        late = spread_scale_factor(20, "aggressive_rhizomatous", 20)
        self.assertGreater(early, 1.0)
        self.assertGreater(late, early)

    def test_asymptote_matches_planting_factor(self):
        from src.planting_spacing import SPREAD_FACTOR
        # At/after maturity the footprint reaches the planting-engine factor.
        self.assertAlmostEqual(
            spread_scale_factor(20, "aggressive_rhizomatous", 20),
            SPREAD_FACTOR["aggressive_rhizomatous"])
        self.assertAlmostEqual(
            spread_scale_factor(99, "self_seeding", 10),
            SPREAD_FACTOR["self_seeding"])

    def test_more_aggressive_spreads_wider(self):
        slow = spread_scale_factor(10, "slow_spreader", 20)
        aggressive = spread_scale_factor(10, "aggressive_rhizomatous", 20)
        self.assertGreater(aggressive, slow)


class TestSpreadAggressiveness(unittest.TestCase):
    def test_year_independent_rate_by_habit(self):
        # 0 for non-spreaders; rises with habit aggressiveness. The 3D viewer
        # multiplies this by the year for continuous colony spread.
        self.assertEqual(spread_aggressiveness(""), 0.0)
        self.assertEqual(spread_aggressiveness("clumping"), 0.0)
        self.assertGreater(spread_aggressiveness("slow_spreader"), 0.0)
        self.assertGreater(spread_aggressiveness("self_seeding"),
                           spread_aggressiveness("slow_spreader"))
        self.assertGreater(spread_aggressiveness("aggressive_rhizomatous"),
                           spread_aggressiveness("self_seeding"))


class TestPlant3DState(unittest.TestCase):
    def test_spread_widens_canopy_not_height(self):
        # An aggressive spreader's footprint grows past its mature canopy over
        # the years while a clumper's does not; height tracks growth only.
        common = {"plant_type": "herb", "years_to_maturity": 10,
                  "growth_curve": "steady", "mature_height_meters": 0.6,
                  "mature_canopy_m": 1.0}
        spreader = dict(common, spread_habit="aggressive_rhizomatous")
        clumper = dict(common, spread_habit="clumping")
        sp = plant_3d_state(spreader, 0, 0, 100)   # mature
        cl = plant_3d_state(clumper, 0, 0, 100)
        self.assertGreater(sp["spread_factor"], 1.0)
        self.assertEqual(cl["spread_factor"], 1.0)
        self.assertGreater(sp["canopy_m"], cl["canopy_m"])
        self.assertAlmostEqual(sp["height_m"], cl["height_m"])  # spread ≠ height
        # Year-independent aggressiveness rate for the 3D colony spread.
        self.assertGreater(sp["spread_rate"], 0.0)
        self.assertEqual(cl["spread_rate"], 0.0)


    def test_woody_plants_never_scatter_a_colony(self):
        # A tree or shrub tagged with a spreading habit must NOT scatter a
        # visible clonal colony in the scene (spread_factor 1.0, spread_rate 0),
        # while a herbaceous plant with the same habit does. Woody plants filling
        # the yard with duplicates is exactly the artefact being fixed.
        for ptype in ("tree", "shrub"):
            woody = {"plant_type": ptype, "years_to_maturity": 10,
                     "growth_curve": "steady", "mature_height_meters": 4.0,
                     "mature_canopy_m": 3.0, "spread_habit": "aggressive_rhizomatous"}
            st = plant_3d_state(woody, 0, 0, 100)   # mature
            self.assertEqual(st["spread_factor"], 1.0, msg=ptype)
            self.assertEqual(st["spread_rate"], 0.0, msg=ptype)
        herb = {"plant_type": "wildflower", "years_to_maturity": 10,
                "growth_curve": "steady", "mature_height_meters": 0.6,
                "mature_canopy_m": 0.5, "spread_habit": "aggressive_rhizomatous"}
        hs = plant_3d_state(herb, 0, 0, 100)
        self.assertGreater(hs["spread_factor"], 1.0)
        self.assertGreater(hs["spread_rate"], 0.0)

    def test_scales_height_and_canopy(self):
        tree = {"plant_type": "tree", "years_to_maturity": 20,
                "growth_curve": "steady", "mature_height_meters": 10.0,
                "mature_canopy_m": 6.0}
        st = plant_3d_state(tree, 53.5, -113.5, 10)   # half-grown
        self.assertAlmostEqual(st["scale_factor"], 0.5)
        self.assertAlmostEqual(st["height_m"], 5.0)
        self.assertAlmostEqual(st["canopy_m"], 3.0)
        self.assertEqual((st["lat"], st["lng"]), (53.5, -113.5))

    def test_presence_for_climax_tree(self):
        # untagged long-lived tree reads as climax → faint when young
        tree = {"plant_type": "tree", "years_to_maturity": 40,
                "mature_height_meters": 15.0}
        st = plant_3d_state(tree, 0, 0, 4)
        self.assertLess(st["presence_opacity"], 1.0)
        self.assertGreaterEqual(st["presence_opacity"], 0.2)

    def test_defaults_when_dimensions_missing(self):
        st = plant_3d_state({"plant_type": "shrub"}, 0, 0, 100)  # fully grown
        self.assertGreater(st["height_m"], 0)
        self.assertGreater(st["canopy_m"], 0)


class TestPlacedPlants3DState(unittest.TestCase):
    _FAKE = {
        1: {"plant_type": "tree", "years_to_maturity": 20, "growth_curve": "steady",
            "mature_height_meters": 10.0, "mature_canopy_m": 6.0},
        2: {"plant_type": "herb", "years_to_maturity": 2},
    }

    def _get(self, pid):
        return self._FAKE.get(pid)

    def test_per_plant_records(self):
        placed = [{"plant_id": 1, "lat": 53.5, "lng": -113.5},
                  {"plant_id": 2, "lat": 53.6, "lng": -113.6}]
        out = placed_plants_3d_state(placed, 10, get_plant=self._get)
        self.assertEqual(len(out), 2)
        self.assertEqual({r["plant_id"] for r in out}, {1, 2})
        tree = next(r for r in out if r["plant_id"] == 1)
        self.assertAlmostEqual(tree["height_m"], 5.0)

    def test_skips_missing_coords(self):
        placed = [{"plant_id": 1, "lat": None, "lng": None},
                  {"plant_id": 2, "lat": 1.0, "lng": 2.0}]
        out = placed_plants_3d_state(placed, 5, get_plant=self._get)
        self.assertEqual([r["plant_id"] for r in out], [2])


if __name__ == "__main__":
    unittest.main()
