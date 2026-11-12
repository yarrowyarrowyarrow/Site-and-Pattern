"""
tests/test_scene_views.py — what the 3D camera frames, and where a neighbour
stands (V3.43, src/scene_views.py).

Until V3.43 every camera was placed from the scene's ``bounds``, floored at
±25 m: the example yard was about 1% of the opening picture, the "sidewalk" view
the before/after page uses stood 22 m outside a 15 x 37 m lot behind a trunk,
and the walker started at the centre of the stage, inside the house. These pin
the two answers that replaced it. Pure arithmetic: no Qt, no database.
"""

import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import scene_views as V                              # noqa: E402
from src.scene_contract import build_scene                    # noqa: E402
from src.project_store import plant_feature                   # noqa: E402

# A 15 x 37 m lot about its own centre, street on the south.
LOT = [[-7.6, -18.3], [7.6, -18.3], [7.6, 18.3], [-7.6, 18.3]]
HOUSE = {"kind": "building", "height_m": 6.5,
         "ring": [[-5.4, -9.3], [5.4, -9.3], [5.4, 2.7], [-5.4, 2.7]]}


def plant(x, y, kind="wildflower", height=0.8, pid=1, **extra):
    return {"plant_id": pid, "x": x, "y": y, "plant_type": kind,
            "height_m": height, "health_state": "healthy", **extra}


FRONT_BED = [plant(-6 + i, -15 + (i % 3)) for i in range(8)]
BACK_BED = [plant(-5 + i, 15) for i in range(6)]


class FocusBoxTest(unittest.TestCase):

    def test_it_is_the_outline_padded_with_no_floor(self):
        box = V.focus_box(LOT, [], [])
        self.assertEqual(box, {"min_x": -9.6, "min_y": -20.3,
                               "max_x": 9.6, "max_y": 20.3})

    def test_a_plant_outside_the_outline_widens_it(self):
        box = V.focus_box(LOT, [plant(12.0, 0.0)], [])
        self.assertEqual(box["max_x"], 14.0)

    def test_a_neighbours_tree_or_house_does_not(self):
        neighbour = {"plant_id": None, "existing": True, "x": 30.0, "y": 0.0,
                     "plant_type": "tree", "height_m": 14.0}
        self.assertEqual(V.focus_box(LOT, [neighbour], []),
                         V.focus_box(LOT, [], []))

    def test_one_plant_is_not_looked_at_from_arms_length(self):
        box = V.focus_box(None, [plant(3.0, 4.0)], [])
        self.assertEqual(box["max_x"] - box["min_x"], V.FOCUS_MIN_SPAN_M)
        self.assertEqual(box["max_y"] - box["min_y"], V.FOCUS_MIN_SPAN_M)
        self.assertEqual((box["min_x"] + box["max_x"]) / 2, 3.0)

    def test_a_structure_counts(self):
        box = V.focus_box(None, [], [{"x": 0.0, "y": 0.0}])
        self.assertIsNotNone(box)

    def test_nothing_placed_frames_the_stage_as_before(self):
        self.assertIsNone(V.focus_box(None, [], []))
        self.assertIsNone(V.focus_box([], [{"plant_id": None, "x": 1, "y": 1}],
                                      []))


class StreetViewTest(unittest.TestCase):

    def test_without_an_outline_there_is_no_street(self):
        self.assertIsNone(V.street_view(None, FRONT_BED, [], 180.0))

    def test_it_stands_a_sidewalk_out_from_the_street_edge(self):
        view = V.street_view(LOT, FRONT_BED + BACK_BED, [HOUSE], 180.0)
        ex, ey = view["eye"]
        self.assertAlmostEqual(ey, -18.3 - V.STREET_STANDOFF_M, places=2)
        self.assertTrue(-8.6 <= ex <= 8.6)
        self.assertEqual(view["bearing"], 180.0)

    def test_it_looks_at_the_planting_on_the_street_side(self):
        view = V.street_view(LOT, FRONT_BED + BACK_BED, [HOUSE], 180.0)
        lx, ly = view["look"]
        self.assertLess(ly, -9.3, "the back bed is behind the house")
        want_x = sum(p["x"] for p in FRONT_BED) / len(FRONT_BED)
        self.assertAlmostEqual(lx, want_x, places=2)

    def test_the_street_can_be_on_any_side(self):
        east = V.street_view(LOT, FRONT_BED, [HOUSE], 90.0)
        self.assertAlmostEqual(east["eye"][0], 7.6 + V.STREET_STANDOFF_M,
                               places=2)
        north = V.street_view(LOT, FRONT_BED + BACK_BED, [HOUSE], 0.0)
        self.assertAlmostEqual(north["eye"][1], 18.3 + V.STREET_STANDOFF_M,
                               places=2)
        self.assertGreater(north["look"][1], 2.7, "now the back bed is the "
                           "street side")

    def test_a_boulevard_tree_is_stepped_round(self):
        """The V3.42 picture: the trunk in the middle of the frame."""
        clear = V.street_view(LOT, FRONT_BED, [HOUSE], 180.0)
        elm = {"plant_id": None, "existing": True, "plant_type": "tree",
               "height_m": 14.0, "x": clear["eye"][0], "y": -20.8}
        moved = V.street_view(LOT, FRONT_BED + [elm], [HOUSE], 180.0)
        self.assertNotEqual(moved["eye"], clear["eye"])
        ex, ey = moved["eye"]
        lx, ly = moved["look"]
        length = math.hypot(lx - ex, ly - ey)
        across = abs((elm["x"] - ex) * (ly - ey)
                     - (elm["y"] - ey) * (lx - ex)) / length
        self.assertGreater(math.hypot(elm["x"] - ex, elm["y"] - ey), 1.2)
        # ... and out of the picture, not just off its centre line: behind the
        # eye, or at a wider angle than half the frame.
        along = ((elm["x"] - ex) * (lx - ex) + (elm["y"] - ey) * (ly - ey)) / length
        self.assertTrue(along <= 0
                        or (across - 0.7) / along >= V._OUT_OF_FRAME - 1e-6,
                        (along, across))
        # Still on the street side of the edge, never inside the yard.
        self.assertLess(ey, -18.3 - 0.9)

    def test_a_tree_in_the_bed_is_part_of_the_picture(self):
        """Only what stands before the yard begins has to leave the frame."""
        clear = V.street_view(LOT, FRONT_BED, [HOUSE], 180.0)
        cherry = plant(clear["look"][0] + 2.0, -12.0, kind="tree", height=6.0,
                       pid=5)
        with_tree = V.street_view(LOT, FRONT_BED + [cherry], [HOUSE], 180.0)
        self.assertEqual(with_tree["eye"][1], clear["eye"][1])
        self.assertLess(abs(with_tree["eye"][0] - clear["eye"][0]), 0.5)

    def test_it_does_not_move_as_plants_grow_or_die(self):
        """The before/after page renders this view at three years, and its
        panels only compare from one spot. So a plant that shade has taken
        still counts toward what is looked at, and a shrub is in the way by
        its grown height, whatever it stands this year."""
        shrub = plant(-2.0, -20.5, kind="shrub", height=0.6, pid=3,
                      mature_height_m=4.0)
        young = V.street_view(LOT, FRONT_BED + [shrub], [HOUSE], 180.0)
        grown = V.street_view(LOT, FRONT_BED + [dict(shrub, height_m=4.0)],
                              [HOUSE], 180.0)
        self.assertEqual(young, grown)
        thinned = [dict(p, health_state="dead", gone="shade") if i % 2 else p
                   for i, p in enumerate(FRONT_BED)]
        self.assertEqual(V.street_view(LOT, thinned, [HOUSE], 180.0),
                         V.street_view(LOT, FRONT_BED, [HOUSE], 180.0))

    def test_the_eye_is_never_inside_a_building(self):
        # A garage built to the street edge, across most of the frontage.
        garage = {"kind": "building", "height_m": 3.0,
                  "ring": [[-7.0, -24.0], [4.0, -24.0], [4.0, -18.0],
                           [-7.0, -18.0]]}
        view = V.street_view(LOT, FRONT_BED, [HOUSE, garage], 180.0)
        self.assertFalse(V._in_ring(view["eye"][0], view["eye"][1],
                                    [tuple(p) for p in garage["ring"]]))

    def test_a_tree_canopy_footprint_is_not_a_wall(self):
        crown = {"kind": "canopy", "height_m": 9.0,
                 "ring": [[-7.0, -24.0], [7.0, -24.0], [7.0, -18.0],
                          [-7.0, -18.0]]}
        self.assertEqual(V.street_view(LOT, FRONT_BED, [crown], 180.0),
                         V.street_view(LOT, FRONT_BED, [], 180.0))

    def test_with_no_plants_it_looks_at_the_middle_of_the_yard(self):
        view = V.street_view(LOT, [], [], 180.0)
        self.assertEqual(view["look"], [0.0, 0.0])


# ── Through build_scene ───────────────────────────────────────────────────────

_LAT, _LNG = 53.5, -113.5
_KY = 111320.0
_KX = 111320.0 * math.cos(math.radians(_LAT))


def _ll(x, y):
    return [_LNG + x / _KX, _LAT + y / _KY]


def _project(street_side=""):
    ring = [_ll(x, y) for x, y in LOT] + [_ll(*LOT[0])]
    feats = [{"type": "Feature",
              "geometry": {"type": "Polygon", "coordinates": [ring]},
              "properties": {"element_type": "property_boundary"}}]
    for p in FRONT_BED:
        lng, lat = _ll(p["x"], p["y"])
        feats.append(plant_feature({"plant_id": 1, "common_name": "Forb",
                                    "lat": lat, "lng": lng}))
    cfg = {"street_side": street_side} if street_side else {}
    return {"type": "FeatureCollection", "properties": {"site_config": cfg},
            "features": feats}


def _get_plant(_pid):
    return {"plant_type": "wildflower", "years_to_maturity": 2,
            "mature_height_meters": 0.8, "mature_canopy_m": 0.5}


class InTheSceneTest(unittest.TestCase):

    def test_a_yard_carries_its_focus_and_its_street_view(self):
        scene = build_scene(_project(), get_plant=_get_plant, wind=False)
        self.assertAlmostEqual(scene["focus"]["max_x"], 9.6, places=1)
        self.assertLess(scene["focus"]["max_x"], scene["bounds"]["max_x"])
        street = scene["views"]["street"]
        self.assertEqual(street["bearing"], 180.0)       # assumed: south
        self.assertAlmostEqual(street["eye"][1], -22.3, places=1)

    def test_the_persons_answer_moves_the_street(self):
        scene = build_scene(_project("east"), get_plant=_get_plant, wind=False)
        street = scene["views"]["street"]
        self.assertEqual(street["bearing"], 90.0)
        self.assertAlmostEqual(street["eye"][0], 11.6, places=1)

    def test_a_design_with_no_outline_has_a_focus_and_no_street(self):
        """A walk through a wild community: the orbit frames its plants, and
        the walker starts where he always did."""
        project = _project()
        project["features"] = project["features"][1:]
        scene = build_scene(project, get_plant=_get_plant, wind=False)
        self.assertEqual(scene["views"], {})
        self.assertIsNotNone(scene["focus"])
        self.assertLess(scene["focus"]["max_x"] - scene["focus"]["min_x"], 20)

    def test_every_year_is_seen_from_the_same_spot(self):
        from tests.test_scene_contract import _get_plant as fixtures
        project = _project()
        lng, lat = _ll(-2.0, -12.0)
        project["features"].append(plant_feature(
            {"plant_id": 7, "common_name": "Aspen", "lat": lat, "lng": lng}))
        for i in range(6):                      # sun forbs the aspen shades out
            lng, lat = _ll(-3.0 + i * 0.4, -11.0)
            project["features"].append(plant_feature(
                {"plant_id": 8, "common_name": "Sun forb",
                 "lat": lat, "lng": lng}))
        scenes = [build_scene(project, year=y, get_plant=fixtures, wind=False)
                  for y in (1, 3, 5, 25)]
        self.assertTrue(any(p.get("gone") for p in scenes[-1]["plants"]),
                        "nothing died, so this proves nothing")
        self.assertEqual(len({json.dumps(sc["views"], sort_keys=True)
                              for sc in scenes}), 1)
        self.assertEqual(len({json.dumps(sc["focus"], sort_keys=True)
                              for sc in scenes}), 1)

    def test_an_empty_design_frames_the_stage(self):
        scene = build_scene({"type": "FeatureCollection", "features": []},
                            get_plant=_get_plant, wind=False)
        self.assertIsNone(scene["focus"])
        self.assertEqual(scene["views"], {})

    def test_the_sprite_gallery_keeps_its_own_stage(self):
        """It frames one specimen by setting ``bounds``; the design's focus
        would have pulled every tile back to 8 m."""
        try:
            from src.sprite_gallery import gallery_scenes
            scenes = gallery_scenes()
        except Exception as exc:                           # noqa: BLE001
            self.skipTest(f"the gallery needs the catalogue: {exc}")
        single = [v["scene"] for k, v in scenes.items() if k != "all"]
        self.assertTrue(single)
        self.assertTrue(all(sc.get("focus") is None for sc in single))


if __name__ == "__main__":
    unittest.main()
