"""
tests/test_vine_habit.py — what a vine holds onto (V2.89, F179).

The owner's rule: *"Vines should climb adjacent plant but only if it is a tree
or shrub."* Everything here pins that rule and the numbers the viewer and the
wildlife both read from it, because the two reading one ``drawn`` block is the
whole point of deciding it in Python (see src/vine_habit.py).
"""

import json
import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_vine_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import vine_habit as V  # noqa: E402

_LAT, _LNG = 53.5, -113.5


def _plant(pid, name, ptype, x, y, h, c, **kw):
    return dict(plant_id=pid, common_name=name, plant_type=ptype, x=x, y=y,
                height_m=h, canopy_m=c, **kw)


def _vine(x=1.5, y=0.0, h=3.0, c=1.5, pid=2):
    return _plant(pid, "Blue Clematis", "vine", x, y, h, c)


def _shrub(x=0.0, y=0.0, h=3.0, c=2.0, pid=1, **kw):
    return _plant(pid, "Saskatoon", "shrub", x, y, h, c, **kw)


def _habit(plants, i=None):
    V.apply_vine_habits(plants)
    vines = [p for p in plants if p["plant_type"] == "vine"]
    return (plants[i] if i is not None else vines[0])["drawn"]


class TheOwnersRule(unittest.TestCase):
    """A tree or a shrub beside it, or nothing."""

    def test_a_vine_beside_a_shrub_climbs_it(self):
        d = _habit([_shrub(), _vine()])
        self.assertEqual(d["habit"], "climbing")
        self.assertEqual(d["support"]["name"], "Saskatoon")
        self.assertEqual(d["support"]["index"], 0)

    def test_a_vine_beside_a_tree_climbs_it(self):
        tree = _plant(1, "Trembling Aspen", "tree", 0, 0, 15.0, 6.0)
        d = _habit([tree, _vine(x=3.5)])
        self.assertEqual(d["habit"], "climbing")
        self.assertEqual(d["support"]["plant_type"], "tree")

    def test_nothing_else_holds_a_vine_up(self):
        """A wildflower, a grass, a groundcover or another vine beside it is
        not something to climb, however close."""
        for ptype in ("wildflower", "herb", "grass", "sedge", "groundcover",
                      "aquatic", "fern", "vine"):
            with self.subTest(ptype):
                other = _plant(1, "Neighbour", ptype, 0, 0, 1.5, 1.0)
                d = _habit([other, _vine(x=0.6)], i=1)
                self.assertEqual(d["habit"], "sprawling")
                self.assertNotIn("support", d)

    def test_nothing_at_all_and_it_sprawls(self):
        self.assertEqual(_habit([_vine()])["habit"], "sprawling")


class Adjacent(unittest.TestCase):
    """Beside means the footprints touch: the gap from the vine's root to the
    host's crown edge is at most the vine's spread radius plus 10 cm."""

    def _gap(self, gap):
        # Shrub radius 1.0, vine spread radius 0.75: root at 1.0 + gap.
        return _habit([_shrub(), _vine(x=1.0 + gap)])["habit"]

    def test_touching_footprints_climb(self):
        self.assertEqual(self._gap(0.75 + V.TOUCH_SLACK_M - 0.01), "climbing")

    def test_a_gap_wider_than_the_vine_reaches_does_not(self):
        self.assertEqual(self._gap(0.75 + V.TOUCH_SLACK_M + 0.01), "sprawling")

    def test_planted_under_the_crown_climbs(self):
        self.assertEqual(self._gap(-0.6), "climbing")

    def test_the_nearest_crown_edge_wins(self):
        near = _shrub(x=0.0, pid=1)
        far = _shrub(x=3.4, pid=3)            # crown edge 0.4 m further off
        near["common_name"], far["common_name"] = "Near", "Far"
        d = _habit([far, near, _vine(x=1.5)], i=2)
        self.assertEqual(d["support"]["name"], "Near")

    def test_a_tie_goes_to_the_earlier_plant(self):
        a, b = _shrub(x=0.0, pid=1), _shrub(x=3.0, pid=3)
        a["common_name"], b["common_name"] = "First", "Second"
        d = _habit([a, b, _vine(x=1.5)], i=2)
        self.assertEqual(d["support"]["name"], "First")


class TheHostHasToBeThere(unittest.TestCase):

    def test_a_dead_host_holds_nothing(self):
        d = _habit([_shrub(health_state="dead"), _vine()], i=1)
        self.assertEqual(d["habit"], "sprawling")

    def test_a_host_not_yet_present_holds_nothing(self):
        d = _habit([_shrub(opacity=V.PRESENT_OPACITY - 0.01), _vine()], i=1)
        self.assertEqual(d["habit"], "sprawling")
        d = _habit([_shrub(opacity=V.PRESENT_OPACITY), _vine()], i=1)
        self.assertEqual(d["habit"], "climbing")


class HowItIsDrawn(unittest.TestCase):

    def test_it_climbs_as_far_as_it_reaches(self):
        tree = _plant(1, "White Spruce", "tree", 0, 0, 15.0, 6.0)
        d = _habit([tree, _vine(x=3.5, h=3.0)])
        self.assertEqual(d["height_m"], 3.0)

    def test_and_no_higher_than_the_host(self):
        d = _habit([_shrub(h=2.0), _vine(h=6.0)])
        self.assertEqual(d["height_m"], 2.0)

    def test_the_foliage_is_on_the_vines_side_of_the_crown(self):
        d = _habit([_shrub(x=0, y=0, c=2.0), _vine(x=0.0, y=1.5)])
        self.assertEqual(d["support"]["toward"], [0.0, 1.0])
        self.assertAlmostEqual(d["x"], 0.0)
        self.assertAlmostEqual(d["y"], 1.0 * 0.75)

    def test_planted_at_the_trunk_still_picks_a_side(self):
        d = _habit([_shrub(), _vine(x=0.0, y=0.0)])
        self.assertEqual(d["support"]["toward"], [1.0, 0.0])

    def test_a_sprawling_vine_lies_low(self):
        d = _habit([_vine(h=6.0, c=1.5)])
        self.assertEqual(d["height_m"], V.SPRAWL_HEIGHT_M)
        self.assertEqual(d["canopy_m"], 1.5)
        self.assertEqual((d["x"], d["y"]), (1.5, 0.0))

    def test_a_vine_shorter_than_the_sprawl_keeps_its_length(self):
        self.assertEqual(_habit([_vine(h=0.2)])["height_m"], 0.2)

    def test_drawn_frame_moves_only_vines(self):
        shrub, vine = _shrub(), _vine()
        V.apply_vine_habits([shrub, vine])
        self.assertIs(V.drawn_frame(shrub), shrub)
        framed = V.drawn_frame(vine)
        self.assertIsNot(framed, vine)
        self.assertEqual((framed["x"], framed["y"], framed["height_m"]),
                         (0.75, 0.0, 3.0))
        self.assertEqual(vine["x"], 1.5, "the record itself is not moved")


class ThroughBuildScene(unittest.TestCase):
    """The decision is made inside build_scene, after existing trees join."""

    RECS = {
        1: {"plant_type": "shrub", "years_to_maturity": 3,
            "mature_height_meters": 3.0, "mature_canopy_m": 2.0,
            "common_name": "Saskatoon"},
        2: {"plant_type": "vine", "years_to_maturity": 2,
            "mature_height_meters": 3.0, "mature_canopy_m": 1.5,
            "common_name": "Blue Clematis"},
    }

    def _scene(self, features):
        from src.scene_contract import build_scene
        return build_scene({"type": "FeatureCollection",
                            "properties": {"site_config": {}},
                            "features": features},
                           get_plant=self.RECS.get, wind=False)

    @staticmethod
    def _at(pid, dx_m, name):
        from src.project_store import plant_feature
        return plant_feature({"plant_id": pid, "common_name": name,
                              "lat": _LAT,
                              "lng": _LNG + dx_m / (111320 * math.cos(
                                  math.radians(_LAT)))})

    def test_a_placed_vine_climbs_a_placed_shrub(self):
        sc = self._scene([self._at(1, 0.0, "Saskatoon"),
                          self._at(2, 1.2, "Blue Clematis")])
        vine = next(p for p in sc["plants"] if p["plant_type"] == "vine")
        self.assertEqual(vine["drawn"]["habit"], "climbing")
        self.assertEqual(sc["plants"][vine["drawn"]["support"]["index"]]
                         ["common_name"], "Saskatoon")
        shrub = next(p for p in sc["plants"] if p["plant_type"] == "shrub")
        self.assertNotIn("drawn", shrub)
        json.dumps(sc)

    def test_an_existing_tree_is_a_tree(self):
        tree = {"type": "Feature",
                "geometry": {"type": "Point", "coordinates": [_LNG, _LAT]},
                "properties": {"element_type": "existing_tree",
                               "height_m": 12.0, "canopy_radius_m": 3.0,
                               "label": "Old spruce"}}
        sc = self._scene([tree, self._at(2, 3.5, "Blue Clematis")])
        vine = next(p for p in sc["plants"] if p["plant_type"] == "vine")
        self.assertEqual(vine["drawn"]["habit"], "climbing")
        self.assertEqual(vine["drawn"]["support"]["name"], "Old spruce")

    def test_alone_it_sprawls(self):
        sc = self._scene([self._at(2, 0.0, "Blue Clematis")])
        self.assertEqual(sc["plants"][0]["drawn"]["habit"], "sprawling")


class AnimalsPerchWhereTheVineIs(unittest.TestCase):
    """A bee visiting a climbing clematis sits on the host's crown, on the
    vine's side, below the top of the vine, not in the air above its root."""

    @classmethod
    def setUpClass(cls):
        from src.db.plants import get_connection, init_db
        init_db()
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, common_name, scientific_name, taxon FROM fauna "
                "WHERE common_name = 'American Bumble Bee'").fetchone()
        finally:
            conn.close()
        cls.bee = dict(row)

    def _creatures(self, plants):
        import src.scene_wildlife as W
        V.apply_vine_habits(plants)
        bee = self.bee

        def edges(pids):
            return [{"id": bee["id"], "plant_id": 2, "taxon": bee["taxon"],
                     "common_name": bee["common_name"],
                     "scientific_name": bee["scientific_name"],
                     "relationship": "nectar"}] if 2 in pids else []
        return W.wildlife_for_scene({"plants": plants, "month": 7,
                                     "is_night": False}, fauna_edges=edges)

    def test_on_a_climbing_vine(self):
        crit = self._creatures([_shrub(x=0, y=0, h=3.0, c=2.0),
                                _vine(x=1.5, y=0, h=3.0, c=1.5)])
        self.assertTrue(crit, "the bumble bee should visit the clematis in July")
        c = crit[0]
        self.assertLess(math.hypot(c["x"] - 0.75, c["y"]),
                        math.hypot(c["x"] - 1.5, c["y"]) + 1e-9,
                        "anchored on the vine's root, not on the host's crown")
        self.assertLessEqual(c["h"], 3.0 + 0.2)
        self.assertGreater(c["h"], V.SPRAWL_HEIGHT_M,
                           "perched as if the vine were lying on the ground")

    def test_on_a_sprawling_vine(self):
        crit = self._creatures([_vine(x=1.5, y=0, h=3.0, c=1.5)])
        self.assertTrue(crit)
        self.assertLessEqual(crit[0]["h"], V.SPRAWL_HEIGHT_M + 0.25,
                             "a bee 3 m up over a vine lying on the ground")


if __name__ == "__main__":
    unittest.main()
