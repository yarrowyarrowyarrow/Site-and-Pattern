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

    def test_a_back_yard_behind_its_house_is_said_to_be_hidden(self):
        """V3.44. The window opens from the street (D5), and a back-yard plan
        seen from there is the front of the house. The view is still where a
        neighbour stands; it says the planting cannot be seen from it."""
        wide = dict(HOUSE, ring=[[-7.4, -9.3], [7.4, -9.3], [7.4, 2.7],
                                 [-7.4, 2.7]])            # wall to wall
        hidden = V.street_view(LOT, BACK_BED, [wide], 180.0)
        self.assertTrue(hidden.get("behind"))
        self.assertAlmostEqual(hidden["eye"][1], -18.3 - V.STREET_STANDOFF_M,
                               delta=6.1)
        seen = V.street_view(LOT, FRONT_BED + BACK_BED, [wide], 180.0)
        self.assertNotIn("behind", seen)
        # All of it at the back is behind too, house or no house: from the
        # street it is a strip across an empty front yard.
        self.assertTrue(V.street_view(LOT, BACK_BED, [], 180.0).get("behind"))
        self.assertTrue(V.street_view(LOT, BACK_BED, [HOUSE], 180.0)
                        .get("behind"))
        # ... which follows the street: from the north it is the front bed
        # that is at the back.
        self.assertNotIn("behind", V.street_view(LOT, BACK_BED, [], 0.0))
        self.assertTrue(V.street_view(LOT, FRONT_BED, [], 0.0).get("behind"))
        # An empty yard has nothing behind anything.
        self.assertNotIn("behind", V.street_view(LOT, [], [HOUSE], 180.0))
        # A trunk in the way is not a wall: it is stepped round, or lived with.
        trunk = plant(-2.5, -19.5, kind="tree", height=14.0, pid=7)
        self.assertNotIn("behind", V.street_view(
            LOT, FRONT_BED + [trunk], [], 180.0))


class OpeningViewTest(unittest.TestCase):
    """Which view a window opens on: the street (the owner's D5) when the
    planting can be seen from it."""

    def test_the_street_when_the_planting_shows_from_it(self):
        street = V.street_view(LOT, FRONT_BED, [HOUSE], 180.0)
        house = V.house_view(LOT, FRONT_BED, [HOUSE])
        self.assertEqual(V.opening_view({"street": street, "house": house}),
                         "street")
        self.assertEqual(V.opening_view({"street": street}), "street")

    def test_the_house_when_it_hides_the_planting(self):
        street = {"eye": [0, -22.3], "look": [0, 15], "behind": True}
        house = {"eye": [0, 3.5], "look": [0, 15]}
        self.assertEqual(V.opening_view({"street": street, "house": house}),
                         "house")

    def test_the_whole_yard_when_there_is_nothing_better(self):
        behind = {"eye": [0, -22.3], "look": [0, 15], "behind": True}
        self.assertEqual(V.opening_view({"street": behind}), "whole")
        self.assertEqual(V.opening_view({}), "whole")
        self.assertEqual(V.opening_view(None), "whole")


# ── From the house (V3.44) ────────────────────────────────────────────────────

GARAGE = {"kind": "building", "height_m": 3.4,
          "ring": [[0.6, 11.3], [7.0, 11.3], [7.0, 17.7], [0.6, 17.7]]}
NEIGHBOUR = {"kind": "building", "height_m": 6.5,
             "ring": [[-20.6, -9.8], [-9.6, -9.8], [-9.6, 3.2], [-20.6, 3.2]]}


class HouseViewTest(unittest.TestCase):
    """Where the person stands at their own house: at the wall most of the
    planting is nearest to, a step outside it, looking at that planting."""

    def test_no_building_in_the_outline_means_no_such_view(self):
        """The app does not guess where a house might be (P9)."""
        self.assertIsNone(V.house_view(LOT, FRONT_BED, []))
        self.assertIsNone(V.house_view(None, FRONT_BED, [HOUSE]))

    def test_a_neighbours_house_is_not_this_yards(self):
        self.assertIsNone(V.house_view(LOT, FRONT_BED, [NEIGHBOUR]))
        self.assertEqual(V.house_view(LOT, FRONT_BED, [NEIGHBOUR, HOUSE]),
                         V.house_view(LOT, FRONT_BED, [HOUSE]))

    def test_the_house_is_the_largest_building_in_the_outline(self):
        ring = V.house_ring(LOT, [GARAGE, HOUSE, NEIGHBOUR])
        self.assertEqual(ring, [tuple(p) for p in HOUSE["ring"]])
        self.assertEqual(V.house_ring(LOT, [GARAGE]),
                         [tuple(p) for p in GARAGE["ring"]])

    def test_a_drawn_tree_crown_is_not_a_house(self):
        crown = dict(HOUSE, kind="canopy")
        self.assertIsNone(V.house_view(LOT, FRONT_BED, [crown]))

    def test_a_front_bed_is_seen_from_the_front_wall(self):
        view = V.house_view(LOT, FRONT_BED, [HOUSE])
        ex, ey = view["eye"]
        self.assertAlmostEqual(ey, -9.3 - V.HOUSE_STEP_M, places=2)
        self.assertTrue(-5.4 < ex < 5.4, "level with the wall, not past it")
        self.assertLess(view["look"][1], ey, "it looks away from the house")

    def test_a_back_bed_is_seen_from_the_back_wall(self):
        view = V.house_view(LOT, BACK_BED, [HOUSE])
        self.assertAlmostEqual(view["eye"][1], 2.7 + V.HOUSE_STEP_M, places=2)
        self.assertGreater(view["look"][1], view["eye"][1])

    def test_the_wall_with_more_of_the_planting_wins(self):
        front = V.house_view(LOT, FRONT_BED, [HOUSE])
        both = V.house_view(LOT, FRONT_BED + BACK_BED, [HOUSE])
        self.assertEqual(both["eye"][1], front["eye"][1])      # 8 against 6
        more_behind = BACK_BED + [plant(-4 + i, 12) for i in range(4)]
        back = V.house_view(LOT, FRONT_BED + more_behind, [HOUSE])
        self.assertGreater(back["eye"][1], 2.7)

    def test_the_eye_is_outside_every_building(self):
        for subject in (FRONT_BED, BACK_BED, FRONT_BED + BACK_BED, []):
            view = V.house_view(LOT, subject, [HOUSE, GARAGE, NEIGHBOUR])
            for b in (HOUSE, GARAGE, NEIGHBOUR):
                self.assertFalse(V._in_ring(*view["eye"],
                                            [tuple(p) for p in b["ring"]]),
                                 (subject[:1], view))

    def test_it_looks_at_least_a_few_metres_out(self):
        """A plant against the wall would otherwise be looked straight down
        on from above it."""
        at_wall = [plant(-1.0 + i * 0.5, -9.6) for i in range(4)]
        view = V.house_view(LOT, at_wall, [HOUSE])
        (ex, ey), (lx, ly) = view["eye"], view["look"]
        self.assertGreaterEqual(math.hypot(lx - ex, ly - ey),
                                V.HOUSE_LOOK_MIN_M - 0.01)

    def test_a_tree_at_the_door_is_stepped_round(self):
        clear = V.house_view(LOT, FRONT_BED, [HOUSE])
        ex, ey = clear["eye"]
        trunk = plant(ex, ey - 1.0, kind="tree", height=12.0, pid=7)
        view = V.house_view(LOT, FRONT_BED + [trunk], [HOUSE])
        self.assertNotEqual(view["eye"], clear["eye"])
        self.assertGreater(math.hypot(view["eye"][0] - ex,
                                      view["eye"][1] - (ey - 1.0)), 1.2)

    def test_it_does_not_stand_in_a_bed_of_tall_plants(self):
        """The first build stood the person in a foundation bed with grasses
        against the lens. Where the wall has clear ground in front of it (a
        path, a doorstep) that is where they stand, and they look across."""
        grasses = [plant(-4.0 + i * 0.5, -10.4 - (i % 2) * 0.6, kind="grass",
                         height=0.3, pid=4, mature_height_m=1.6)
                   for i in range(11)]                    # x from -4 to 1
        view = V.house_view(LOT, grasses, [HOUSE])
        ex, ey = view["eye"]
        near = [g for g in grasses
                if math.hypot(g["x"] - ex, g["y"] - ey) < V._CROWD_NEAR_M]
        self.assertEqual(near, [], view)
        self.assertAlmostEqual(ey, -9.3 - V.HOUSE_STEP_M, places=2)
        self.assertTrue(-5.4 < ex < 5.4)
        self.assertLess(view["look"][0], ex, "it looks across at the bed")
        # Low plants at the foot of the wall are no reason to move.
        low = [dict(g, mature_height_m=0.4) for g in grasses]
        at_the_bed = V.house_view(LOT, low, [HOUSE])
        self.assertLess(at_the_bed["eye"][0], ex)
        # A bed along the whole wall: the least crowded spot, and still a view.
        whole = [plant(-5.2 + i * 0.5, -10.2, kind="grass", height=0.3, pid=4,
                       mature_height_m=1.6) for i in range(22)]
        self.assertIsNotNone(V.house_view(LOT, whole, [HOUSE]))
        # The same answer while the grasses are still small or after they die.
        grown = [dict(g, height_m=1.6) for g in grasses]
        dead = [dict(g, gone="shade") for g in grasses]
        self.assertEqual(V.house_view(LOT, grown, [HOUSE]), view)
        self.assertEqual(V.house_view(LOT, dead, [HOUSE]), view)

    def test_it_does_not_move_as_plants_grow_or_die(self):
        """As the street view: the before/after panels only compare from one
        spot."""
        young = [dict(p, height_m=0.1) for p in FRONT_BED]
        gone = [dict(p, gone="shade", health_state="dead") for p in FRONT_BED]
        shrub = [plant(-2.5, -11.5, kind="shrub", height=0.4, pid=3,
                       mature_height_m=3.0)]
        base = V.house_view(LOT, FRONT_BED + shrub, [HOUSE])
        self.assertEqual(V.house_view(LOT, young + shrub, [HOUSE]), base)
        self.assertEqual(V.house_view(LOT, gone + shrub, [HOUSE]), base)
        grown = [dict(shrub[0], height_m=3.0)]
        self.assertEqual(V.house_view(LOT, FRONT_BED + grown, [HOUSE]), base)
        recruit = [plant(0.0, 10.0, recruit=True) for _ in range(40)]
        self.assertEqual(V.house_view(LOT, FRONT_BED + shrub + recruit,
                                      [HOUSE]), base)

    def test_with_nothing_planted_it_looks_at_the_yard(self):
        view = V.house_view(LOT, [], [HOUSE])
        self.assertIsNotNone(view)
        self.assertFalse(V._in_ring(*view["look"],
                                    [tuple(p) for p in HOUSE["ring"]]))


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

    def test_a_walk_through_a_wild_community_has_a_focus_and_no_street(self):
        """The orbit frames its plants, and the walker starts where he always
        did, at the centre its layout leaves clear for him."""
        project = _project()
        project["features"] = project["features"][1:]
        project["properties"]["reference_version"] = 3
        scene = build_scene(project, get_plant=_get_plant, wind=False)
        self.assertEqual(scene["views"], {})
        self.assertIsNotNone(scene["focus"])
        self.assertLess(scene["focus"]["max_x"] - scene["focus"]["min_x"], 20)

    def test_a_yard_with_nothing_outlined_is_seen_from_its_street_side(self):
        """V3.44. The simple app's usual design is a pin and a bed, with no
        outline (V3.28), and it had no street view: the camera fell back to a
        guess south of the stage. Its own extent stands in for the outline,
        and the person's answer about the street still moves it."""
        project = _project()
        project["features"] = project["features"][1:]
        scene = build_scene(project, get_plant=_get_plant, wind=False)
        street = scene["views"]["street"]
        focus = scene["focus"]
        self.assertAlmostEqual(street["eye"][1],
                               focus["min_y"] - V.STREET_STANDOFF_M, places=1)
        self.assertGreater(street["look"][1], street["eye"][1])
        project["properties"]["site_config"]["street_side"] = "east"
        east = build_scene(project, get_plant=_get_plant, wind=False)
        self.assertAlmostEqual(east["views"]["street"]["eye"][0],
                               east["focus"]["max_x"] + V.STREET_STANDOFF_M,
                               places=1)
        years = {json.dumps(build_scene(project, year=y, get_plant=_get_plant,
                                        wind=False)["views"], sort_keys=True)
                 for y in (1, 5, 25)}
        self.assertEqual(len(years), 1, "the same spot in every year")

    def test_with_nothing_outlined_the_house_is_the_one_under_the_pin(self):
        project = _project()
        project["features"] = project["features"][1:]
        ring = [_ll(x, y) for x, y in HOUSE["ring"]]
        house = {"type": "Feature",
                 "geometry": {"type": "Polygon",
                              "coordinates": [ring + [ring[0]]]},
                 "properties": {"element_type": "canopy_footprint",
                                "shape_type": "Building (OSM)",
                                "height_m": 6.5}}
        project["features"].append(house)
        no_pin = build_scene(project, get_plant=_get_plant, wind=False)
        self.assertNotIn("house", no_pin["views"],
                         "nothing says which building is this yard's")
        lng, lat = _ll(0.0, -3.0)                    # on the house
        project["properties"]["site_config"].update(latitude=lat,
                                                    longitude=lng)
        scene = build_scene(project, get_plant=_get_plant, wind=False)
        self.assertIn("house", scene["views"])
        lng, lat = _ll(0.0, -14.0)                   # on the lawn
        project["properties"]["site_config"].update(latitude=lat,
                                                    longitude=lng)
        lawn = build_scene(project, get_plant=_get_plant, wind=False)
        self.assertNotIn("house", lawn["views"])

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

    def test_a_house_in_the_outline_gives_a_view_from_it(self):
        project = _project()
        self.assertNotIn("house", build_scene(
            project, get_plant=_get_plant, wind=False)["views"])
        ring = [_ll(x, y) for x, y in HOUSE["ring"]]
        project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]},
            "properties": {"element_type": "canopy_footprint",
                           "shape_type": "Building (OSM)", "height_m": 6.5}})
        scenes = [build_scene(project, year=y, get_plant=_get_plant,
                              wind=False) for y in (1, 5, 25)]
        house = scenes[0]["views"]["house"]
        self.assertAlmostEqual(house["eye"][1], -9.3 - V.HOUSE_STEP_M,
                               places=1)
        self.assertEqual(len({json.dumps(sc["views"], sort_keys=True)
                              for sc in scenes}), 1,
                         "the same spot in every year")

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
