"""
tests/test_succession_engine.py — the Temporal Succession Engine (V2.21).

Guards the biology behind the growth timeline: a growing overstory casts shade
that closes over understory plants year by year, and sun-loving species that
get over-topped past their tolerance decline and die, while shade-tolerant
neighbours inherit the understory — so the year-N scene is the *climax
community*, not every plant frozen at full health.

Pure Python — injected ``get_plant``, no Qt, no DB, no network, in the same
spirit as tests/test_scene_contract.py / tests/test_succession.py.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.succession_engine import (   # noqa: E402
    SuccessionEngine, evaluate_project, shade_ceiling,
    static_casters_from_project, GROWTH_MATRIX_YEARS,
)
from src.project_store import plant_feature   # noqa: E402

_LAT, _LNG = 53.5, -113.5
_M = 111320.0   # metres per degree latitude (app's cosLat metric)

# A fast-closing deciduous overstory tree, a sun-loving understory forb, and a
# shade-tolerant understory forb. Dimensions use the DB-side keys get_plant
# returns (mature_height_meters / mature_canopy_m).
_ASPEN = {"plant_type": "tree", "years_to_maturity": 12, "growth_curve": "fast_early",
          "mature_height_meters": 11.0, "mature_canopy_m": 8.0,
          "deciduous_evergreen": "deciduous", "common_name": "Aspen"}
_SUN_FORB = {"plant_type": "wildflower", "years_to_maturity": 2, "growth_curve": "steady",
             "mature_height_meters": 0.6, "mature_canopy_m": 0.4,
             "sun_requirement": "full_sun", "common_name": "Sun forb"}
_SHADE_FORB = {"plant_type": "wildflower", "years_to_maturity": 2, "growth_curve": "steady",
               "mature_height_meters": 0.6, "mature_canopy_m": 0.4,
               "sun_requirement": "partial_shade,full_shade", "common_name": "Shade forb"}

_FAKE = {10: _ASPEN, 20: _SUN_FORB, 30: _SHADE_FORB}


def _get_plant(pid):
    return _FAKE.get(pid)


def _north(metres):
    """A latitude offset ``metres`` north (Edmonton's sun is southern, so a
    plant's shadow — and its neighbour's — falls to the north)."""
    return metres / _M


def _placed(*rows):
    """rows: (plant_id, north_m, [east_m]) → placed-plant records."""
    out = []
    for r in rows:
        pid, dn = r[0], r[1]
        de = r[2] if len(r) > 2 else 0.0
        out.append({"plant_id": pid, "common_name": _FAKE[pid].get("common_name", ""),
                    "lat": _LAT + _north(dn),
                    "lng": _LNG + de / (_M * 0.6)})
    return out


class TestShadeCeiling(unittest.TestCase):
    def test_full_sun_is_least_tolerant(self):
        self.assertLess(shade_ceiling("full_sun"),
                        shade_ceiling("partial_shade"))

    def test_full_shade_never_stressed(self):
        self.assertEqual(shade_ceiling("full_shade"), 1.0)

    def test_multivalue_takes_most_tolerant(self):
        # A plant that lists several tolerances "fits" if ANY does → the most
        # forgiving ceiling wins (matches the rest of the app's any-of reading).
        self.assertEqual(shade_ceiling("partial_shade,full_shade"), 1.0)
        self.assertEqual(shade_ceiling("full_sun,partial_shade"),
                         shade_ceiling("partial_shade"))

    def test_unknown_is_forgiving_not_lethal(self):
        # No requirement → a mid ceiling, never 0 — we don't invent mortality
        # for a plant whose light needs we can't read (P9).
        self.assertGreater(shade_ceiling(""), 0.35)
        self.assertGreater(shade_ceiling(None), 0.35)


class TestNoCompetition(unittest.TestCase):
    def test_year_zero_all_healthy(self):
        # Year 0 is the mature-design reference; nothing has been shaded out yet.
        eng = SuccessionEngine(_placed((10, 0), (20, 2)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        out = eng.evaluate_year(0)
        self.assertEqual(out["counts"]["dead"], 0)
        self.assertTrue(all(p["state"] == "healthy" for p in out["plants"]))
        self.assertEqual(out["delta"], [])

    def test_lone_plant_never_declines(self):
        eng = SuccessionEngine(_placed((20, 0)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        for y in (1, 5, 15, 30):
            out = eng.evaluate_year(y)
            self.assertEqual(out["plants"][0]["state"], "healthy")
            self.assertEqual(out["plants"][0]["shade_fraction"], 0.0)

    def test_open_plant_beyond_canopy_survives(self):
        # A forb well beyond the aspen's mature canopy (12 m north) keeps its
        # light and stays healthy across the whole horizon.
        eng = SuccessionEngine(_placed((10, 0), (20, 12)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        forb = eng.evaluate_year(30)["plants"][1]
        self.assertEqual(forb["state"], "healthy")


class TestShadeOut(unittest.TestCase):
    def test_sun_lover_under_canopy_dies_over_time(self):
        # The canonical scenario: a full-sun forb under a fast aspen is healthy
        # at planting, then declines and dies as the canopy closes over it.
        eng = SuccessionEngine(_placed((10, 0), (20, 2)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))

        def forb(y):
            return eng.evaluate_year(y)["plants"][1]

        self.assertEqual(forb(0)["state"], "healthy")
        # Health is monotone non-increasing as the canopy only grows.
        healths = [forb(y)["health"] for y in range(0, 26)]
        for earlier, later in zip(healths, healths[1:]):
            self.assertLessEqual(later, earlier + 1e-9)
        # By maturity it has been shaded to death.
        self.assertEqual(forb(25)["state"], "dead")
        self.assertEqual(forb(25)["health"], 0.0)
        # It passes through a "declining" band on the way (never a bare flip).
        self.assertTrue(any(forb(y)["state"] == "declining" for y in range(1, 26)))

    def test_shade_tolerant_neighbour_survives_same_spot(self):
        # Sun-lover and shade-lover the same 2 m north of the aspen: the sun-
        # lover dies, the shade-lover inherits the understory. The climax
        # community is not "everything survives".
        eng = SuccessionEngine(
            _placed((10, 0), (20, 2), (30, 2, 1.5)),
            get_plant=_get_plant, origin=(_LAT, _LNG))
        by_name = {p["common_name"]: p for p in eng.evaluate_year(25)["plants"]}
        self.assertEqual(by_name["Sun forb"]["state"], "dead")
        self.assertEqual(by_name["Shade forb"]["state"], "healthy")

    def test_delta_reports_only_diminished_plants(self):
        eng = SuccessionEngine(_placed((10, 0), (20, 2), (30, 2, 1.5)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        delta = eng.evaluate_year(25)["delta"]
        self.assertEqual([d["common_name"] for d in delta], ["Sun forb"])
        self.assertTrue(delta[0]["overtopped"])

    def test_overstory_tree_itself_is_never_shaded(self):
        # The tallest plant casts, it is not a receiver of shorter neighbours.
        eng = SuccessionEngine(_placed((10, 0), (20, 2)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        aspen = eng.evaluate_year(25)["plants"][0]
        self.assertEqual(aspen["state"], "healthy")


class TestStaticCasters(unittest.TestCase):
    def test_existing_tree_shades_understory_from_year_one(self):
        # An existing mature tree (a static caster) shades a sun-forb planted
        # under it from the very start — it declines without any design tree.
        project = {"features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
             "properties": {"element_type": "existing_tree",
                            "height_m": 12.0, "canopy_radius_m": 5.0}},
            plant_feature({"plant_id": 20, "common_name": "Sun forb",
                           "lat": _LAT + _north(2.0), "lng": _LNG}),
        ]}
        statics = static_casters_from_project(project)
        self.assertEqual(len(statics), 1)
        self.assertEqual(statics[0]["kind"], "tree")
        out = evaluate_project(project, 20, get_plant=_get_plant,
                               origin=(_LAT, _LNG))
        forb = next(p for p in out["plants"] if p["common_name"] == "Sun forb")
        self.assertIn(forb["state"], ("declining", "dead"))
        self.assertTrue(forb["overtopped"])


class TestGrowthMatrix(unittest.TestCase):
    def test_matrix_grows_then_plateaus(self):
        eng = SuccessionEngine(_placed((10, 0)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        m = eng.growth_matrix(0)
        self.assertEqual(sorted(m), sorted(GROWTH_MATRIX_YEARS))
        heights = [m[y]["height_m"] for y in GROWTH_MATRIX_YEARS]
        for earlier, later in zip(heights, heights[1:]):
            self.assertLessEqual(earlier, later)          # non-decreasing
        self.assertLess(heights[0], heights[-1])          # actually grew
        self.assertAlmostEqual(m[30]["height_m"], 11.0, delta=0.01)  # matured


class TestContract(unittest.TestCase):
    def test_evaluate_year_is_json_serialisable(self):
        out = evaluate_project(
            {"type": "FeatureCollection", "features": [
                plant_feature({"plant_id": 10, "common_name": "Aspen",
                               "lat": _LAT, "lng": _LNG}),
                plant_feature({"plant_id": 20, "common_name": "Sun forb",
                               "lat": _LAT + _north(2.0), "lng": _LNG}),
            ]}, 15, get_plant=_get_plant, origin=(_LAT, _LNG))
        json.dumps(out)   # must not raise
        for key in ("year", "counts", "plants", "delta"):
            self.assertIn(key, out)

    def test_missing_coords_keep_index_alignment(self):
        # A record with no position is skipped for evaluation but must not
        # shift the indices of the plants that follow it.
        placed = [{"plant_id": 20, "lat": None, "lng": None},
                  {"plant_id": 10, "lat": _LAT, "lng": _LNG},
                  {"plant_id": 20, "lat": _LAT + _north(2.0), "lng": _LNG}]
        eng = SuccessionEngine(placed, get_plant=_get_plant, origin=(_LAT, _LNG))
        out = eng.evaluate_year(25)
        indices = {p["index"] for p in out["plants"]}
        self.assertEqual(indices, {1, 2})    # index 0 (no coords) dropped
        under = next(p for p in out["plants"] if p["index"] == 2)
        self.assertEqual(under["state"], "dead")

    def test_empty_design(self):
        eng = SuccessionEngine([], get_plant=_get_plant)
        out = eng.evaluate_year(10)
        self.assertEqual(out["plants"], [])
        self.assertEqual(out["delta"], [])


if __name__ == "__main__":
    unittest.main()
