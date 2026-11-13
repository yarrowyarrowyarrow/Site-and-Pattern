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
# An evergreen overstory the same size as the aspen — casts opaque shade all
# season (no leaf-off break), so the same understory plant fares worse under it.
_SPRUCE = {"plant_type": "tree", "years_to_maturity": 12, "growth_curve": "fast_early",
           "mature_height_meters": 11.0, "mature_canopy_m": 8.0,
           "deciduous_evergreen": "evergreen", "common_name": "Spruce"}
# A part-shade forb: fine in real understory shade, but not under a dense
# evergreen crown all season.
_PART_FORB = {"plant_type": "wildflower", "years_to_maturity": 2, "growth_curve": "steady",
              "mature_height_meters": 0.6, "mature_canopy_m": 0.4,
              "sun_requirement": "partial_shade", "common_name": "Part forb"}
# A slow young full-sun tree that gets overtopped early by a taller evergreen —
# genuinely shade-stressed, yet as a canopy species it is suppressed (declining),
# not culled the way an understory forb would be.
_SAPLING = {"plant_type": "tree", "years_to_maturity": 25, "growth_curve": "slow_start",
            "mature_height_meters": 6.0, "mature_canopy_m": 4.0,
            "sun_requirement": "full_sun", "common_name": "Sapling"}
# A self-seeding herbaceous native that colonises the gaps left by shaded-out
# plants (tolerates part shade, so it fits an understory gap).
_SEEDER = {"plant_type": "wildflower", "years_to_maturity": 3, "growth_curve": "steady",
           "mature_height_meters": 0.7, "mature_canopy_m": 0.5,
           "sun_requirement": "full_sun,partial_shade",
           "spread_habit": "self_seeding", "common_name": "Selfseeder"}

_FAKE = {10: _ASPEN, 20: _SUN_FORB, 30: _SHADE_FORB,
         40: _SPRUCE, 50: _PART_FORB, 60: _SAPLING, 70: _SEEDER}


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


class TestLeafOff(unittest.TestCase):
    def test_part_shade_survives_under_deciduous_canopy(self):
        # A part-shade forb directly under a deciduous aspen keeps enough
        # spring/fall light to thrive — the leaf-off break puts the crown's
        # effective shade below the plant's tolerance. This is the "many plants
        # handle part shade" correctness fix.
        eng = SuccessionEngine(_placed((10, 0), (50, 1)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        forb = eng.evaluate_year(25)["plants"][1]
        self.assertEqual(forb["common_name"], "Part forb")
        self.assertEqual(forb["state"], "healthy")

    def test_part_shade_struggles_under_evergreen_canopy(self):
        # The same part-shade forb under an evergreen of the same size fares
        # worse — a dense crown that never drops its leaves shades all season.
        eng = SuccessionEngine(_placed((40, 0), (50, 1)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        forb = eng.evaluate_year(25)["plants"][1]
        self.assertIn(forb["state"], ("declining", "dead"))

    def test_deciduous_shades_less_than_evergreen(self):
        # Same understory plant, same geometry: the deciduous overstory leaves it
        # healthier than the evergreen does.
        decid = SuccessionEngine(_placed((10, 0), (50, 1)),
                                 get_plant=_get_plant, origin=(_LAT, _LNG))
        everg = SuccessionEngine(_placed((40, 0), (50, 1)),
                                 get_plant=_get_plant, origin=(_LAT, _LNG))
        self.assertGreater(decid.evaluate_year(25)["plants"][1]["health"],
                           everg.evaluate_year(25)["plants"][1]["health"])


class TestTreesSuppressedNotKilled(unittest.TestCase):
    def test_overtopped_sapling_declines_but_never_dies(self):
        # A slow young full-sun tree shaded early by a taller evergreen is
        # suppressed, but a canopy species grows toward the light rather than
        # being culled like a forb.
        eng = SuccessionEngine(_placed((40, 0), (60, 1)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))

        def sapling(y):
            return next(p for p in eng.evaluate_year(y)["plants"]
                        if p["common_name"] == "Sapling")

        # It is genuinely stressed (overtopped, off full health)…
        self.assertTrue(sapling(25)["overtopped"])
        self.assertLess(sapling(25)["health"], 1.0)
        # …but never dead, across the whole horizon.
        for y in range(0, 26):
            self.assertNotEqual(sapling(y)["state"], "dead")

    def test_forb_in_the_same_spot_still_dies(self):
        # Contrast: a full-sun forb under the same evergreen is still mortal —
        # the exemption is for canopy trees only, not a blanket immortality.
        eng = SuccessionEngine(_placed((40, 0), (20, 1)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        forb = eng.evaluate_year(25)["plants"][1]
        self.assertEqual(forb["state"], "dead")


class TestRegeneration(unittest.TestCase):
    def _eng(self):
        # Aspen overstory; a full-sun forb that gets shaded out 2 m north; a
        # self-seeding native 8 m away to colonise the gap.
        return SuccessionEngine(
            _placed((10, 0), (20, 2), (70, 8)),
            get_plant=_get_plant, origin=(_LAT, _LNG))

    def test_no_recruits_before_anything_dies(self):
        eng = self._eng()
        for y in (0, 3, 8):
            self.assertEqual(eng.recruits(y), [],
                             f"nothing has died by year {y}")

    def test_gap_is_colonised_after_a_death(self):
        eng = self._eng()
        # By maturity the forb is dead and its gap has been recruited into.
        self.assertEqual(eng.evaluate_year(25)["counts"]["dead"], 1)
        rc = eng.recruits(25)
        self.assertEqual(len(rc), 1)
        r = rc[0]
        self.assertEqual(r["plant_id"], 70)           # the self-seeder colonised
        self.assertEqual(r["into"], "Sun forb")       # the gap it filled
        self.assertGreaterEqual(r["age"], 0)          # established, growing in

    def test_recruit_lags_the_death(self):
        # A recruit only appears a couple of seasons after the gap opens, and its
        # age tracks the slider so it visibly grows in.
        eng = self._eng()
        ages = {}
        for y in range(0, 26):
            rc = eng.recruits(y)
            if rc:
                ages[y] = rc[0]["age"]
        self.assertTrue(ages, "the gap should eventually be colonised")
        first = min(ages)
        self.assertEqual(ages[first], 0)              # just established
        self.assertGreater(ages[max(ages)], ages[first])  # grows with the years

    def test_only_self_seeding_herbs_recruit(self):
        # With no self-seeder present, a dead plant's gap stays bare — nothing is
        # invented (P9); only species already in the design colonise.
        eng = SuccessionEngine(_placed((10, 0), (20, 2)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        self.assertEqual(eng.evaluate_year(25)["counts"]["dead"], 1)
        self.assertEqual(eng.recruits(25), [])

    def test_recruits_deterministic(self):
        a = self._eng().recruits(25)
        b = self._eng().recruits(25)
        self.assertEqual(a, b)


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


# ── buildings cast shade from their walls (V3.46) ────────────────────────────

_KX = _M * __import__("math").cos(__import__("math").radians(_LAT))


def _building(x0, y0, x1, y1, height, *, radius=None):
    """A scanned building as the app stores one: a canopy_footprint whose
    ``canopy_radius_m`` is its enclosing circle (osm_features.ring_radius_m)."""
    import math
    ring = [[_LNG + x / _KX, _LAT + y / _M]
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]
    if radius is None:
        radius = math.hypot(x1 - x0, y1 - y0) / 2
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring]},
            "properties": {"element_type": "canopy_footprint",
                           "shape_type": "Building (OSM)", "cast_shade": True,
                           "height_m": height, "canopy_radius_m": radius}}


def _forb_at(x, y, pid=20, name="Sun forb"):
    return plant_feature({"plant_id": pid, "common_name": name,
                          "lat": _LAT + y / _M, "lng": _LNG + x / _KX})


class TestABuildingIsItsWallsNotACircle(unittest.TestCase):
    """The V3.43 review found 37% of a fresh plan "lost to shade" by the fifth
    summer. V3.46 asked the model what shaded them: 82 of the 136 were plants
    near a 3.4 m garage, counted as *under* it because a building was a circle
    out to its farthest corner (6 m on a garage 3.2 m to each wall)."""

    #: A garage 6.4 m square, 3.4 m tall, centred on the origin.
    GARAGE = (-3.2, -3.2, 3.2, 3.2, 3.4)

    def _engine(self, *plants, building=None):
        project = {"features": [_building(*(building or self.GARAGE))]
                   + list(plants)}
        from src.project_store import plant_record_from_feature
        recs = [plant_record_from_feature(f) for f in plants]
        return SuccessionEngine(
            recs, get_plant=_get_plant, origin=(_LAT, _LNG),
            static_casters=static_casters_from_project(project))

    def test_the_caster_keeps_its_outline(self):
        statics = static_casters_from_project(
            {"features": [_building(*self.GARAGE)]})
        self.assertEqual(statics[0]["kind"], "building")
        self.assertTrue(statics[0]["footprint"])
        self.assertAlmostEqual(statics[0]["radius_m"], 4.525, places=2)

    def test_a_plant_beside_the_south_wall_is_in_full_sun(self):
        """One metre south of the wall, inside the enclosing circle: nothing
        is between it and the sun at any hour sampled."""
        eng = self._engine(_forb_at(0.0, -4.2))
        self.assertEqual(eng.experienced_shade(0, 10), 0.0)
        self.assertEqual(eng.evaluate_year(25)["counts"]["dead"], 0)
        self.assertIsNone(eng.main_shader(0, 10))

    def test_a_plant_at_the_east_wall_is_shaded_part_of_the_day_only(self):
        """Morning sun, afternoon shade: never the 0.9 of standing under a
        crown, and a plant that takes part shade lives."""
        eng = self._engine(_forb_at(4.0, 0.0),
                           _forb_at(4.0, 0.0, pid=50, name="Part forb"))
        shade = eng.experienced_shade(0, 10)
        self.assertGreater(shade, 0.0)
        self.assertLess(shade, 0.6)
        self.assertEqual(eng.evaluate_year(25)["plants"][1]["state"], "healthy")

    def test_a_plant_close_under_the_north_wall_is_in_its_shadow(self):
        eng = self._engine(_forb_at(0.0, 3.8))
        self.assertGreater(eng.experienced_shade(0, 10), 0.6)
        shader = eng.main_shader(0, 10)
        self.assertEqual(shader["kind"], "static")
        self.assertFalse(shader["is_tree"])

    def test_the_shadow_ends_where_the_wall_is_too_low_to_reach(self):
        """A 3.4 m wall's noon shadow in June is under 2 m long: a plant 8 m
        north of it is shaded only when the sun is low."""
        eng = self._engine(_forb_at(0.0, 3.8), _forb_at(0.0, 11.2))
        self.assertLess(eng.experienced_shade(1, 10),
                        eng.experienced_shade(0, 10))

    def test_a_building_with_no_outline_keeps_its_circle(self):
        """A building marked as a point has only a size, so its shadow is the
        circle's, as before: nothing to the south of it is shaded."""
        project = {"features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
            "properties": {"element_type": "existing_building",
                           "height_m": 6.0, "canopy_radius_m": 4.0}}]}
        from src.project_store import plant_record_from_feature
        south, north = _forb_at(0.0, -5.0), _forb_at(0.0, 5.0)
        eng = SuccessionEngine(
            [plant_record_from_feature(south), plant_record_from_feature(north)],
            get_plant=_get_plant, origin=(_LAT, _LNG),
            static_casters=static_casters_from_project(project))
        self.assertEqual(eng.experienced_shade(0, 10), 0.0)
        self.assertGreater(eng.experienced_shade(1, 10), 0.5)

    def test_a_tree_is_still_a_crown_to_stand_under(self):
        project = {"features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
            "properties": {"element_type": "existing_tree", "height_m": 12.0,
                           "canopy_radius_m": 5.0, "tree_foliage": "evergreen"}}]}
        from src.project_store import plant_record_from_feature
        forb = _forb_at(0.0, -3.0)
        eng = SuccessionEngine(
            [plant_record_from_feature(forb)], get_plant=_get_plant,
            origin=(_LAT, _LNG),
            static_casters=static_casters_from_project(project))
        self.assertGreaterEqual(eng.experienced_shade(0, 10), 0.9)
        shader = eng.main_shader(0, 10)
        self.assertTrue(shader["is_tree"])
        self.assertEqual(shader["foliage"], "evergreen")


class TestSweptOutline(unittest.TestCase):

    SQUARE = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]

    def test_inside_the_outline_and_inside_its_shadow(self):
        from src.succession_engine import in_swept_ring
        self.assertTrue(in_swept_ring(1.0, 1.0, 0.0, 3.0, self.SQUARE))
        self.assertTrue(in_swept_ring(1.0, 4.0, 0.0, 3.0, self.SQUARE))

    def test_past_the_shadows_end_and_beside_it(self):
        from src.succession_engine import in_swept_ring
        self.assertFalse(in_swept_ring(1.0, 5.5, 0.0, 3.0, self.SQUARE))
        self.assertFalse(in_swept_ring(3.0, 3.0, 0.0, 3.0, self.SQUARE))
        self.assertFalse(in_swept_ring(1.0, -1.0, 0.0, 3.0, self.SQUARE))

    def test_a_shadow_cast_at_an_angle(self):
        from src.succession_engine import in_swept_ring
        self.assertTrue(in_swept_ring(4.0, 4.0, 3.0, 3.0, self.SQUARE))
        self.assertFalse(in_swept_ring(4.0, 0.5, 3.0, 3.0, self.SQUARE))


class TestAHerbIsNotAnEvergreen(unittest.TestCase):
    """A herbaceous plant is not above ground from October to May. Until V3.46
    it shaded the plants at its foot as a spruce would, all year."""

    _TALL = {"plant_type": "wildflower", "years_to_maturity": 2,
             "growth_curve": "steady", "mature_height_meters": 1.8,
             "mature_canopy_m": 0.9, "deciduous_evergreen": "herbaceous",
             "common_name": "Tall forb"}
    _LOW = {"plant_type": "groundcover", "years_to_maturity": 1,
            "growth_curve": "steady", "mature_height_meters": 0.15,
            "mature_canopy_m": 0.45,
            "sun_requirement": "full_sun,partial_shade",
            "common_name": "Low mat"}

    def _engine(self, tall):
        plants = {1: tall, 2: self._LOW}
        return SuccessionEngine(
            [{"plant_id": 1, "lat": _LAT, "lng": _LNG},
             {"plant_id": 2, "lat": _LAT + 0.2 / _M, "lng": _LNG}],
            get_plant=plants.get, origin=(_LAT, _LNG))

    def test_a_mat_under_a_tall_wildflower_lives(self):
        eng = self._engine(self._TALL)
        self.assertLess(eng.experienced_shade(1, 10), 0.7)
        self.assertEqual(eng.evaluate_year(25)["plants"][1]["state"], "healthy")

    def test_the_same_mat_under_an_evergreen_of_that_size_does_not(self):
        eng = self._engine(dict(self._TALL, deciduous_evergreen="evergreen"))
        self.assertGreaterEqual(eng.experienced_shade(1, 10), 0.9)
        self.assertEqual(eng.evaluate_year(25)["plants"][1]["state"], "dead")

    def test_unknown_foliage_is_still_opaque(self):
        tall = dict(self._TALL)
        tall.pop("deciduous_evergreen")
        eng = self._engine(tall)
        self.assertGreaterEqual(eng.experienced_shade(1, 10), 0.9)


class TestWhatShadesAPlant(unittest.TestCase):

    def test_the_stronger_of_two_casters_is_named(self):
        # A spruce overhead and an aspen further off: the spruce.
        eng = SuccessionEngine(
            _placed((40, 0), (20, 1.0), (10, 9.0)),
            get_plant=_get_plant, origin=(_LAT, _LNG))
        shader = eng.main_shader(1, 15)
        self.assertEqual((shader["kind"], shader["index"]), ("plant", 0))
        self.assertEqual(shader["common_name"], "Spruce")
        self.assertLessEqual(shader["share"], eng.experienced_shade(1, 15))

    def test_nothing_overtops_it_and_year_zero(self):
        eng = SuccessionEngine(_placed((20, 0), (30, 2.0)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        self.assertIsNone(eng.main_shader(0, 10))
        eng = SuccessionEngine(_placed((40, 0), (20, 1.0)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        self.assertIsNone(eng.main_shader(1, 0))

    def test_a_sole_casters_share_is_the_plants_whole_shade(self):
        eng = SuccessionEngine(_placed((40, 0), (20, 1.0)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        for year in (3, 8, 20):
            shader = eng.main_shader(1, year)
            if shader is None:
                self.assertEqual(eng.experienced_shade(1, year), 0.0)
            else:
                self.assertAlmostEqual(shader["share"],
                                       eng.experienced_shade(1, year), places=3)

    def test_death_year_is_the_first_dead_year(self):
        eng = SuccessionEngine(_placed((40, 0), (20, 1.0)),
                               get_plant=_get_plant, origin=(_LAT, _LNG))
        died = eng.death_year(1, 25)
        self.assertIsNotNone(died)
        self.assertEqual(eng.evaluate_year(died)["plants"][1]["state"], "dead")
        self.assertNotEqual(
            eng.evaluate_year(died - 1)["plants"][1]["state"], "dead")


if __name__ == "__main__":
    unittest.main()
