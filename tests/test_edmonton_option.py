"""
tests/test_edmonton_option.py — "Edmonton natives only" reaches every surface
that chooses a plant (F220, V3.12).

The owner's ask had two halves: the option itself, and that it "extend into
plant communities too with the ones containing non native (to Edmonton) plants
not showing up". V2.85 is the warning about the second half: the province rule
reached the plant pool and Bur Oak still arrived by community, then a
Saskatchewan yard's April bloom by the critic's repair. So each door is tried
here: the search, the community library and its page, the generator's pool,
its communities, its repairs, and the AI path's name resolver.
"""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_edmonton_test_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
import src.db.plants as _plants_mod  # noqa: E402
import src.permadesign_api as _api  # noqa: E402
import src.llm_design as llm  # noqa: E402
from src import native_here as nh  # noqa: E402

EDMONTON = (53.5190, -113.4960)


def setUpModule():
    from src.db.plants import init_db
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    init_db()
    _api._DB_READY = True
    nh.set_document(None)


def _yard(lat, lng, w=12.0, h=18.0):
    dlat, dlng = w / 111320.0, h / (111320.0 * math.cos(math.radians(lat)))
    return [(lat, lng), (lat + dlat, lng), (lat + dlat, lng + dlng),
            (lat, lng + dlng)]


def _local():
    return nh.native_names("edmonton")


class TestTheSearch(unittest.TestCase):

    def test_native_near_keeps_only_the_list(self):
        from src.db.plants import search_plants
        rows = search_plants(native_near="edmonton")
        self.assertEqual({r["scientific_name"] for r in rows}, set(_local()))
        names = {r["common_name"] for r in rows}
        self.assertIn("Saskatoon Berry", names)
        for gone in ("Eastern Red Columbine", "Yellow Columbine",
                     "Red Columbine", "Bur Oak", "Glacier Lily"):
            self.assertNotIn(gone, names)

    def test_it_narrows_alongside_the_other_filters(self):
        from src.db.plants import search_plants
        shrubs = search_plants(plant_type=["shrub"], native_near="edmonton")
        self.assertTrue(shrubs)
        self.assertTrue(all(r["plant_type"] == "shrub" for r in shrubs))
        self.assertLess(len(shrubs), len(search_plants(plant_type=["shrub"])))


class TestTheCommunityLibrary(unittest.TestCase):

    def test_a_community_with_one_outsider_is_hidden(self):
        from src.db import polycultures as P
        index = P.get_library_index()
        by_name = {e["name"]: cid for cid, e in index.items()}
        # Bur Oak Community holds Saskatchewan's oak; the index names it.
        oak = index[by_name["Bur Oak Community"]]
        self.assertIn("Bur Oak", oak["not_around"]["edmonton"])
        shown = P.filter_library(index, native_near="edmonton")
        self.assertNotIn(by_name["Bur Oak Community"], shown)
        for cid in shown:
            self.assertEqual(index[cid]["not_around"]["edmonton"], [],
                             index[cid]["name"])
        self.assertLess(len(shown), len(P.filter_library(index)))

    def test_an_unknown_place_is_refused(self):
        from src.db import polycultures as P
        with self.assertRaises(ValueError):
            P.filter_library(P.get_library_index(), native_near="calgary")

    def test_the_page_names_the_plants_that_are_not_native_here(self):
        from src.community_page import around_line
        from src.db import polycultures as P
        oak = P.get_polyculture_by_id(
            P.get_polyculture_by_name("Bur Oak Community")["id"])
        line = around_line(oak["members"])
        self.assertTrue(line.startswith("Not native around Edmonton: "), line)
        self.assertIn("Bur Oak", line)
        self.assertEqual(line.count("Bur Oak"), 1)
        native = [m for m in oak["members"]
                  if m["scientific_name"] in _local()]
        self.assertEqual(around_line(native),
                         "Every plant here is native around Edmonton.")
        self.assertEqual(around_line([]), "")


class TestTheGenerator(unittest.TestCase):

    def test_the_goal_reaches_the_site_filters(self):
        self.assertEqual(llm._with_local({"zone": 4}, ["edmonton_native"]),
                         {"zone": 4, "native_near": "edmonton"})
        self.assertEqual(llm._with_local({"zone": 4}, ["native_only"]),
                         {"zone": 4})

    def test_communities_follow_the_list(self):
        kept = llm._communities_for_site(
            _api.list_polycultures(), {"native_near": "edmonton"}, 0.0)
        from src.db.polycultures import get_polyculture_by_id
        for c in kept:
            for m in get_polyculture_by_id(c["id"])["members"]:
                self.assertIn(m["scientific_name"], _local(), c["name"])
        self.assertNotIn("Bur Oak Community", {c["name"] for c in kept})

    def test_a_model_naming_a_non_local_plant_does_not_get_it(self):
        """The resolver retries a named plant with no filters so a model's
        choice is never silently dropped; it must still keep the user's."""
        got = llm._resolve_plants([{"common_name": "Bur Oak"}],
                                  _api.query_plants,
                                  {"native_near": "edmonton"})
        self.assertEqual(got, [])
        got = llm._resolve_plants([{"common_name": "Saskatoon Berry"}],
                                  _api.query_plants,
                                  {"native_near": "edmonton"})
        self.assertEqual(len(got), 1)

    def test_an_offline_design_for_an_edmonton_yard_is_all_local(self):
        """Pool, communities, repairs and top-ups together."""
        from src.db.plants import get_plant
        lat, lng = EDMONTON
        project = llm.generate_design_offline(
            boundary=_yard(lat, lng),
            site_config={"latitude": lat, "longitude": lng,
                         "ecoregion_key": "aspen_parkland",
                         "hardiness_zone": 4},
            goals=["edmonton_native", "pollinator"])
        rows = [get_plant(p["plant_id"]) or {} for p in project.placed_plants]
        self.assertGreaterEqual(len(rows), 20)
        strays = sorted({r.get("common_name") for r in rows
                         if r.get("scientific_name") not in _local()})
        self.assertEqual(strays, [])

    def test_the_palette_the_model_sees_is_the_list(self):
        lat, lng = EDMONTON
        text = llm._plant_palette(
            _api.query_plants,
            llm._with_local(llm._site_filters(
                {"latitude": lat, "longitude": lng}), ["edmonton_native"]),
            site=EDMONTON, area_m2=216.0)
        self.assertTrue(text)
        for gone in ("Yellow Columbine", "Glacier Lily", "Bur Oak"):
            self.assertNotIn(gone, text)


if __name__ == "__main__":
    unittest.main()
