"""
tests/test_site_fit.py — recommending for the yard, not the region (V2.85).

F154: the design generator judged "fits this site" at ecoregion scale (three
records anywhere in Aspen Parkland, which runs from Calgary to Winnipeg) and
filtered nativity on the Alberta flag wherever the pin was, so an Edmonton yard
was offered Saskatchewan's Bur Oak. F155: capacity was counted in 6 m anchor
cells, so a 216 m^2 yard "held" six plants and got four or five.

These pin the rules, then the outcome on real yards, with no network (the
suite's offline guard) and no LLM.
"""

import math
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_site_fit_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402
import src.llm_design as llm  # noqa: E402
from src import site_fit  # noqa: E402

EDMONTON = (53.5190, -113.4960)
REGINA = (50.4450, -104.6180)
WINNIPEG = (49.8951, -97.1384)


def _use_our_db() -> None:
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True


def _yard(lat, lng, w=12.0, h=18.0):
    dlat, dlng = w / 111320.0, h / (111320.0 * math.cos(math.radians(lat)))
    return [(lat, lng), (lat + dlat, lng), (lat + dlat, lng + dlng),
            (lat, lng + dlng)]


class TestWhichProvince(unittest.TestCase):

    def test_the_110th_meridian_decides(self):
        self.assertEqual(site_fit.province_at(52.0, -110.01), "AB")
        self.assertEqual(site_fit.province_at(52.0, -109.99), "SK")
        self.assertEqual(site_fit.province_at(*EDMONTON), "AB")
        self.assertEqual(site_fit.province_at(*REGINA), "SK")

    def test_outside_the_two_provinces_there_is_no_answer(self):
        self.assertEqual(site_fit.province_at(*WINNIPEG), "")
        self.assertEqual(site_fit.province_at(49.28, -123.10), "")   # Vancouver
        self.assertEqual(site_fit.province_at(None, None), "")


class TestHowNear(unittest.TestCase):
    """The rules on a grid of our own, then two real answers."""

    def setUp(self):
        site_fit._grid.cache_clear()
        i, j = site_fit._index(53.5), site_fit._index(-113.5)
        grid = {"Here here": {(i, j): 4},
                "Near near": {(i + 2, j): 1},
                "Far away": {(i + 20, j + 20): 50}}
        self._patch = mock.patch.object(site_fit, "_grid", return_value=grid)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        site_fit._grid.cache_clear()

    def test_the_four_answers(self):
        self.assertEqual(site_fit.locality("Here here", 53.52, -113.49), "here")
        self.assertEqual(site_fit.locality("Near near", 53.52, -113.49), "near")
        self.assertEqual(site_fit.locality("Far away", 53.52, -113.49),
                         "elsewhere")
        self.assertEqual(site_fit.locality("Nobody", 53.52, -113.49),
                         "unrecorded")

    def test_unrecorded_is_not_ranked_below_elsewhere(self):
        """P9: an empty square is unsurveyed as often as unoccupied."""
        self.assertEqual(site_fit.LOCALITY_RANK["unrecorded"],
                         site_fit.LOCALITY_RANK["elsewhere"])
        self.assertGreater(site_fit.LOCALITY_RANK["here"],
                           site_fit.LOCALITY_RANK["near"])

    def test_no_site_ranks_everything_level(self):
        self.assertEqual(site_fit.locality_rank("Here here", None, None), 0)


class TestHowNearOnTheRealGrid(unittest.TestCase):

    def setUp(self):
        site_fit._grid.cache_clear()

    def test_saskatoon_berry_is_recorded_around_edmonton(self):
        self.assertEqual(site_fit.locality("Amelanchier alnifolia", *EDMONTON),
                         "here")

    def test_the_mountain_and_dry_south_species_are_not(self):
        for sci in ("Valeriana sitchensis", "Aster alpinus",
                    "Gutierrezia sarothrae"):
            self.assertEqual(site_fit.locality(sci, *EDMONTON), "elsewhere",
                             sci)


class TestTheRules(unittest.TestCase):

    def test_the_site_filters_carry_the_province(self):
        lat, lng = EDMONTON
        self.assertEqual(llm._site_filters(
            {"latitude": lat, "longitude": lng})["native_province"], "AB")
        lat, lng = REGINA
        self.assertEqual(llm._site_filters(
            {"latitude": lat, "longitude": lng})["native_province"], "SK")
        lat, lng = WINNIPEG
        self.assertNotIn("native_province", llm._site_filters(
            {"latitude": lat, "longitude": lng}))

    def test_the_province_supersedes_the_alberta_flag(self):
        self.assertEqual(llm._without_superseded_native(
            {"native_province": "SK", "native_only": True}),
            {"native_province": "SK"})
        self.assertEqual(llm._without_superseded_native({"native_only": True}),
                         {"native_only": True})
        self.assertEqual(llm._native_default({"native_province": "AB"}), {})
        self.assertEqual(llm._native_default({}), {"native_only": True})

    def test_a_yard_gets_a_finer_anchor_grid_and_a_lot_keeps_six_metres(self):
        self.assertAlmostEqual(llm._boundary_area_m2(_yard(*EDMONTON)), 216.0,
                               delta=2.0)
        self.assertEqual(llm._anchor_spacing_m(_yard(*EDMONTON)),
                         llm._MIN_ANCHOR_SPACING_M)
        self.assertEqual(llm._anchor_spacing_m(_yard(*EDMONTON, 80, 80)),
                         llm._SPACING_M)

    def test_a_bur_oak_is_too_big_for_a_front_yard_not_for_acreage(self):
        oak = {"mature_canopy_m": 15.0, "spacing_meters": 10.0}
        self.assertTrue(llm._too_big_for(oak, 216.0))
        self.assertFalse(llm._too_big_for(oak, 3600.0))
        self.assertFalse(llm._too_big_for({}, 216.0))

    def test_nothing_is_dropped_when_everything_is_too_big(self):
        oaks = [{"mature_canopy_m": 15.0}, {"mature_canopy_m": 20.0}]
        self.assertEqual(llm._fits_the_area(oaks, 100.0), oaks)


class TestTheYard(unittest.TestCase):
    """Real yards, the offline generator end to end."""

    @classmethod
    def setUpClass(cls):
        _use_our_db()
        site_fit._grid.cache_clear()

    def _design(self, where, goals=None):
        lat, lng = where
        return llm.generate_design_offline(
            boundary=_yard(lat, lng),
            site_config={"latitude": lat, "longitude": lng,
                         "ecoregion_key": "aspen_parkland",
                         "hardiness_zone": 4},
            goals=goals)

    def _rows(self, project):
        from src.db.plants import get_plant
        return [get_plant(p["plant_id"]) or {} for p in project.placed_plants]

    def test_a_goal_no_longer_drops_the_native_requirement(self):
        """Bur Oak reached an Edmonton yard with the pollinator goal ticked."""
        for goals in (None, ["pollinator"], ["pet_friendly", "kid_friendly"]):
            rows = self._rows(self._design(EDMONTON, goals))
            strays = sorted({r.get("common_name") for r in rows
                             if "AB" not in (r.get("native_provinces") or "")
                             .split(",")})
            self.assertEqual(strays, [], f"goals={goals}")

    def test_a_front_yard_is_filled(self):
        """Four or five plants on 216 m^2 before V2.85."""
        rows = self._rows(self._design(EDMONTON, ["pollinator"]))
        names = [r.get("common_name") for r in rows]
        self.assertGreaterEqual(len(names), 50)
        self.assertGreaterEqual(len(set(names)), 10)

    def test_no_one_species_is_the_design(self):
        from collections import Counter
        rows = self._rows(self._design(EDMONTON))
        top = Counter(r.get("common_name") for r in rows).most_common(1)[0][1]
        self.assertLessEqual(top, 0.30 * len(rows))

    def test_woody_plants_stay_inside_their_share_of_the_ground(self):
        """Ten chokecherries, eleven saskatoons and seventeen vines once."""
        rows = self._rows(self._design(EDMONTON, ["pollinator"]))
        woody = [r for r in rows if r.get("plant_type") in llm._WOODY_TYPES]
        foot = sum(float(r.get("mature_canopy_m") or r.get("spacing_meters")
                         or 0) ** 2 for r in woody)
        # The budget binds the density pass; the critic's repairs and the
        # communities may add a few more, hence the headroom.
        self.assertLess(foot, 0.6 * 216.0)

    def test_the_palette_the_model_sees_follows_the_same_rules(self):
        """The AI path picks from this list, and it showed the first eight of
        each type in alphabetical order, Bur Oak among the trees."""
        lat, lng = EDMONTON
        text = llm._plant_palette(
            _api.query_plants,
            llm._site_filters({"latitude": lat, "longitude": lng}),
            site=EDMONTON, area_m2=216.0)
        self.assertTrue(text)
        self.assertNotIn("Bur Oak", text)
        self.assertNotIn("Sitka Valerian", text)

    def test_the_bur_oak_community_is_not_offered_in_alberta(self):
        comms = _api.list_polycultures()
        fit = llm._communities_for_site(
            comms, {"native_province": "AB"}, 216.0)
        self.assertNotIn("Bur Oak Community", {c.get("name") for c in fit})
        self.assertIn("Bur Oak Community", {c.get("name") for c in comms})


if __name__ == "__main__":
    unittest.main()
