"""
tests/test_scene_season.py — the season the 3D preview draws (V3.46, F263).

The V3.43 review's finding 7: a perennial stood at its July height on 21 April
and was green in January's snow, a shrub kept its leaves all winter beside a
bare tree, and the months were typed into five of the viewer's chunks.
``src/scene_season.py`` decides the season once, from the region pack's frost
dates; these hold its rules, what reaches the scene, and that the viewer and
the animals read the same figure.
"""

import os
import re
import sys
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import region_climate, scene_season, scene_wildlife  # noqa: E402
from src.project_store import plant_feature                   # noqa: E402
from src.scene_contract import build_scene                    # noqa: E402
from tests.test_scene_contract import _FAKE_PLANTS            # noqa: E402

_LAT, _LNG = 53.5, -113.5
TORONTO = {"latitude": 43.65, "longitude": -79.38}

HERB = {"plant_type": "wildflower", "foliage_type": "herbaceous",
        "bloom_start": 7, "bloom_end": 8}
CROCUS = dict(HERB, bloom_start=4, bloom_end=5)
ASTER = dict(HERB, bloom_start=8, bloom_end=10)
GRASS = {"plant_type": "grass", "foliage_type": "herbaceous"}
TREE = {"plant_type": "tree", "foliage_type": "deciduous"}
SHRUB = {"plant_type": "shrub", "foliage_type": "deciduous"}
SPRUCE = {"plant_type": "tree", "foliage_type": "evergreen"}


def _on(month, day=21):
    return datetime(2025, month, day, 13, 0)


def _js(name):
    with open(os.path.join(ROOT, "html", "scene3d", name),
              encoding="utf-8") as fh:
        return fh.read()


class TheCalendarIsThePacks(unittest.TestCase):

    def setUp(self):
        self.cal = scene_season.calendar({})

    def test_its_dates_are_the_frost_dates_plus_the_stated_offsets(self):
        frost = region_climate.frost_dates({})
        last = datetime(2025, *frost["last"]).timetuple().tm_yday
        first = datetime(2025, *frost["first"]).timetuple().tm_yday
        self.assertEqual(self.cal["herb_start"],
                         last - scene_season.HERB_START_BEFORE)
        self.assertEqual(self.cal["herb_full"],
                         last + scene_season.HERB_FULL_AFTER)
        self.assertEqual(self.cal["leaf_start"],
                         last - scene_season.LEAF_START_BEFORE)
        self.assertEqual(self.cal["leaf_full"],
                         last + scene_season.LEAF_FULL_AFTER)
        self.assertEqual(self.cal["turn_start"],
                         first - scene_season.TURN_BEFORE)
        self.assertEqual(self.cal["down"], first + scene_season.DOWN_AFTER)

    def test_another_frost_date_moves_the_season(self):
        """A second region's pack is a folder: its dates move the picture with
        no code change."""
        later = dict(self.cal)
        for key in ("thaw", "herb_start", "herb_full", "leaf_start",
                    "leaf_full"):
            later[key] += 21                 # a last frost three weeks later
        here = scene_season.plant_season(TREE, _on(5), self.cal)
        there = scene_season.plant_season(TREE, _on(5), later)
        self.assertEqual(here["look"], "young")
        self.assertEqual(there["look"], "bare")

    def test_it_says_where_the_dates_came_from(self):
        words = scene_season.basis_words(self.cal)
        frost = region_climate.frost_dates({})
        self.assertIn(region_climate.date_words(frost["last"]), words)
        self.assertIn(region_climate.date_words(frost["first"]), words)
        self.assertIn("typical for the", words)
        self.assertIn("not this year's weather", words)

    def test_outside_the_provinces_nothing_claims_the_dates_are_that_places(self):
        cal = scene_season.calendar(TORONTO)
        self.assertFalse(cal["known"])
        words = scene_season.basis_words(cal)
        self.assertIn("No frost dates are known for this place", words)
        self.assertNotIn("frost May", words)
        # …and the picture is still drawn, by the default pack's dates.
        self.assertEqual(
            scene_season.plant_season(TREE, _on(1), cal)["look"], "bare")

    def test_the_calendar_is_read_once(self):
        self.assertIs(scene_season.calendar({}), scene_season.calendar({}))


class AHerbThroughTheYear(unittest.TestCase):

    def setUp(self):
        self.cal = scene_season.calendar({})

    def _look(self, plant, month):
        return scene_season.plant_season(plant, _on(month), self.cal)

    def test_dry_stems_stand_through_the_winter(self):
        for month in (11, 12, 1, 2, 3):
            self.assertEqual(self._look(HERB, month), {"look": "dry"}, month)

    def test_it_is_a_hand_high_in_april_and_most_of_the_way_up_in_may(self):
        """Finding 7: perennials stood at July height on 21 April."""
        april, may = self._look(HERB, 4), self._look(HERB, 5)
        self.assertEqual(april["look"], "young")
        self.assertLess(april["up"], 0.3)
        self.assertGreaterEqual(april["up"], scene_season.UP_MIN)
        self.assertEqual(may["look"], "young")
        self.assertTrue(0.45 < may["up"] < 0.9, may)
        self.assertGreater(may["up"], april["up"])

    def test_summer_is_plain_green_and_carries_no_height(self):
        for month in (6, 7, 8):
            self.assertEqual(self._look(HERB, month), {"look": "green"}, month)

    def test_it_turns_in_september_and_is_dry_by_late_october(self):
        september = self._look(HERB, 9)
        self.assertEqual(september["look"], "turning")
        self.assertTrue(0.2 < september["t"] < 0.8, september)
        self.assertEqual(self._look(HERB, 10), {"look": "dry"})

    def test_a_plant_in_flower_is_up_and_is_not_dry(self):
        """Prairie Crocus in April stands at flowering height while its
        neighbours are a hand high; an aster still in flower in October has
        not gone to straw."""
        self.assertEqual(self._look(CROCUS, 4)["look"], "green")
        self.assertNotIn("up", self._look(CROCUS, 4))
        october = self._look(ASTER, 10)
        self.assertEqual(october["look"], "turning")
        self.assertLessEqual(october["t"], scene_season.TURN_IN_FLOWER)
        march = self._look(dict(HERB, bloom_start=3, bloom_end=5), 3)
        self.assertEqual(march["look"], "young")
        self.assertGreaterEqual(march["up"], scene_season.UP_IN_FLOWER)

    def test_nothing_starts_before_the_thaw(self):
        start, full = scene_season.herb_rise(self.cal, bloom_start=3)
        self.assertGreaterEqual(start, self.cal["thaw"])
        self.assertGreater(full, start)

    def test_up_only_ever_grows_through_the_spring(self):
        last = 0.0
        for month, day in [(4, d) for d in range(1, 31)] + \
                          [(5, d) for d in range(1, 32)] + \
                          [(6, d) for d in range(1, 31)]:
            s = scene_season.plant_season(HERB, _on(month, day), self.cal)
            if s["look"] == "dry":
                continue
            up = s.get("up", 1.0)
            self.assertGreaterEqual(up, last, (month, day))
            last = up
        self.assertEqual(last, 1.0)


class LeavesDropAlike(unittest.TestCase):

    def setUp(self):
        self.cal = scene_season.calendar({})

    def test_a_shrub_is_bare_exactly_when_a_tree_is(self):
        """Finding 7: trees went bare from November to March and shrubs never
        did."""
        for month in range(1, 13):
            tree = scene_season.plant_season(TREE, _on(month), self.cal)
            shrub = scene_season.plant_season(SHRUB, _on(month), self.cal)
            self.assertEqual(tree, shrub, month)

    def test_the_year_of_a_deciduous_plant(self):
        looks = [scene_season.plant_season(TREE, _on(m), self.cal)["look"]
                 for m in range(1, 13)]
        self.assertEqual(looks, ["bare", "bare", "bare", "bare", "young",
                                 "green", "green", "green", "turning", "bare",
                                 "bare", "bare"])

    def test_an_evergreen_carries_no_season(self):
        for month in (1, 4, 7, 10):
            self.assertIsNone(
                scene_season.plant_season(SPRUCE, _on(month), self.cal))
            self.assertIsNone(scene_season.plant_season(
                dict(HERB, foliage_type="evergreen"), _on(month), self.cal))

    def test_a_semi_evergreen_keeps_its_leaves_bronzed(self):
        semi = dict(SHRUB, foliage_type="semi-evergreen")
        self.assertEqual(
            scene_season.plant_season(semi, _on(1), self.cal), {"look": "held"})
        self.assertEqual(
            scene_season.plant_season(semi, _on(7), self.cal), {"look": "green"})

    def test_a_body_that_keeps_itself_carries_none(self):
        cactus = dict(HERB, drawn={"body": "pads", "height_m": 0.3})
        self.assertIsNone(scene_season.plant_season(cactus, _on(1), self.cal))

    def test_a_floating_leaf_dies_back_and_never_shrinks(self):
        lily = dict(HERB, drawn={"body": "floating", "height_m": 1.0})
        self.assertEqual(
            scene_season.plant_season(lily, _on(1), self.cal), {"look": "dry"})
        self.assertNotIn("up", scene_season.plant_season(lily, _on(5), self.cal))


class TheGroundTurnsWithIt(unittest.TestCase):

    def test_the_year_of_the_unplanted_ground(self):
        cal = scene_season.calendar({})
        got = [scene_season.apply_seasons([], _on(m), {})["ground"]
               for m in range(1, 13)]
        self.assertEqual(got, ["snow", "snow", "snow", "waking", "green",
                               "green", "green", "green", "turning", "dormant",
                               "snow", "snow"])
        self.assertTrue(set(got) <= set(scene_season.GROUNDS))
        self.assertTrue(cal["known"])

    def test_snow_is_november_to_march(self):
        for month in range(1, 13):
            self.assertEqual(
                scene_season.apply_seasons([], _on(month), {})["snow"],
                month in (11, 12, 1, 2, 3), month)


# ── what reaches the scene ───────────────────────────────────────────────────

def _yard(*plants):
    feats = []
    for pid, x in plants:
        feats.append(plant_feature({
            "plant_id": pid, "common_name": f"p{pid}",
            "lat": _LAT, "lng": _LNG + x * 1e-5}))
    return {"type": "FeatureCollection", "properties": {"site_config": {}},
            "features": feats}


class TheSceneCarriesIt(unittest.TestCase):

    def _scene(self, month, year=5):
        return build_scene(_yard((3, 0), (6, 2), (5, 4), (7, 8)), year=year,
                           get_plant=_FAKE_PLANTS.get, wind=False,
                           when=_on(month))

    def test_the_block_and_every_plant_that_is_not_evergreen(self):
        scene = self._scene(1)
        self.assertEqual(scene["season"]["ground"], "snow")
        self.assertTrue(scene["season"]["snow"])
        self.assertEqual(scene["season"]["leaves"], "bare")
        self.assertEqual(scene["season"]["herbs"], "dry")
        self.assertIn("typical for the", scene["season"]["basis"])
        by = {p["plant_id"]: p for p in scene["plants"]}
        self.assertEqual(by[3]["season"], {"look": "dry"})       # a forb
        self.assertEqual(by[6]["season"], {"look": "bare"})      # a shrub
        self.assertEqual(by[7]["season"], {"look": "bare"})      # an aspen
        self.assertNotIn("season", by[5])                        # a spruce
        for look in (p["season"]["look"] for p in scene["plants"]
                     if "season" in p):
            self.assertIn(look, scene_season.LOOKS)

    def test_a_plant_keeps_its_own_height_and_the_season_rides_beside_it(self):
        """``height_m`` is this YEAR's height and a dozen things read it; the
        season is a share beside it, never a change to it."""
        july, april = self._scene(7), self._scene(4)
        for a, b in zip(july["plants"], april["plants"]):
            self.assertEqual(a["height_m"], b["height_m"])
            self.assertEqual(a["canopy_m"], b["canopy_m"])
        forb = next(p for p in april["plants"] if p["plant_id"] == 3)
        self.assertLess(forb["season"]["up"], 0.3)

    def test_where_to_stand_does_not_move_with_the_month(self):
        july, january = self._scene(7), self._scene(1)
        self.assertEqual(july["focus"], january["focus"])
        self.assertEqual(july["views"], january["views"])

    def test_an_existing_tree_has_a_season_too(self):
        project = _yard((3, 0))
        project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [_LNG, _LAT + 1e-4]},
            "properties": {"element_type": "existing_tree", "height_m": 10.0,
                           "canopy_radius_m": 3.0,
                           "tree_foliage": "deciduous"}})
        scene = build_scene(project, year=5, get_plant=_FAKE_PLANTS.get,
                            wind=False, when=_on(1))
        tree = next(p for p in scene["plants"] if p.get("existing"))
        self.assertEqual(tree["season"], {"look": "bare"})


# ── one figure for the viewer and the animals ────────────────────────────────

class TheViewerAndTheAnimalsAgree(unittest.TestCase):

    def test_an_animal_perches_at_the_height_the_plant_is_drawn(self):
        plant = {"plant_type": "wildflower", "height_m": 1.0}
        self.assertEqual(scene_wildlife._drawn_height(plant), 1.0)
        plant["season"] = {"look": "young", "up": 0.25}
        self.assertEqual(scene_wildlife._drawn_height(plant), 0.25)
        mat = {"plant_type": "groundcover", "height_m": 0.6,
               "season": {"look": "young", "up": 0.5}}
        self.assertAlmostEqual(scene_wildlife._drawn_height(mat),
                               scene_wildlife.GROUNDCOVER_DRAWN_MAX_M * 0.5)
        reed = {"plant_type": "aquatic", "height_m": 2.0,
                "drawn": {"body": "reed", "height_m": 1.6},
                "season": {"look": "young", "up": 0.5}}
        self.assertAlmostEqual(scene_wildlife._drawn_height(reed), 0.8)

    def test_the_viewer_draws_by_the_same_two_numbers(self):
        """bodyHeightOf is the V2.88 answer times the season's share, and it
        is still what everything that sits on a plant asks."""
        season = _js("01d-season.js")
        self.assertRegex(
            season, r"function bodyHeightOf\(p\) \{ return "
                    r"fullBodyHeightOf\(p\) \* seasonUp\(p\); \}")
        self.assertIn("function fullBodyHeightOf(p)", _js("04-quality.js"))
        self.assertNotIn("function bodyHeightOf", _js("04-quality.js"))

    def test_every_look_python_decides_the_viewer_can_draw(self):
        table = re.search(r"const SEASON_LOOK = \{(.*?)\n\};",
                          _js("01d-season.js"), re.S)
        self.assertIsNotNone(table, "01d-season.js: SEASON_LOOK moved")
        drawn = set(re.findall(r"^\s{2}(\w+):", table.group(1), re.M))
        self.assertEqual(drawn, set(scene_season.LOOKS))

    def test_every_ground_python_decides_the_viewer_knows(self):
        src = _js("01d-season.js") + _js("02-plants.js") + _js("02c-site.js")
        for ground in scene_season.GROUNDS:
            self.assertRegex(src, rf"(?<!\w){ground}(?!\w)\s*[':]", ground)

    def test_the_chunk_loads_before_anything_that_draws_a_plant(self):
        with open(os.path.join(ROOT, "html", "scene3d", "chunks.js"),
                  encoding="utf-8") as fh:
            files = re.findall(r"'scene3d/([\w-]+\.js)'", fh.read())
        self.assertIn("01d-season.js", files)
        self.assertLess(files.index("01d-season.js"),
                        files.index("02-plants.js"))

    def test_no_chunk_keeps_a_month_rule_of_its_own(self):
        """"November to March" was typed into five chunks. The month rules
        live in 01d-season.js alone, for a scene that does not say."""
        folder = os.path.join(ROOT, "html", "scene3d")
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".js") or name in ("01d-season.js",
                                                    "chunks.js"):
                continue
            src = _js(name)
            if name == "01-core.js":
                # seasonalColor: the fallback 01d-season.js calls for a plant
                # with no season of its own (an evergreen, an older scene).
                start = src.index("function seasonalColor(")
                src = src[:start] + src[src.index("let renderer;"):]
            self.assertNotRegex(
                src, r"(?:[mM]onth\s*(?:>=|<=|===)\s*\d"
                     r"|\bm\s*(?:>=\s*11|<=\s*3|===\s*(?:4|10))\b)", name)
            for gone in ("_bareMonth(", "_isDecid("):
                self.assertNotIn(gone, src, f"{name} asks {gone}…) itself")


if __name__ == "__main__":
    unittest.main()
