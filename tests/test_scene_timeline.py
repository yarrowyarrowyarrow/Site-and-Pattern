"""
tests/test_scene_timeline.py — what the years did to a plan, said where and
which (V3.46, F263; decision D4).

The V3.43 review's finding 6: the preview quietly kills the plan. The line
over the picture counted the losses and said nothing a person could act on.
``src/scene_timeline.py`` says where (the drawn area), which plants, and what
shades them (the shade model's own answer). These hold its words and that the
scene's notes are the scene's own losses, no more and no fewer.
"""

import os
import sys
import unittest
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from src import scene_site, scene_timeline as tl               # noqa: E402
from src.scene_contract import build_scene                     # noqa: E402

BOX = {"min_x": -8.0, "max_x": 8.0, "min_y": -18.0, "max_y": 18.0}
SOUTH = 180.0


def _square(x, y, half=2.0):
    return [[x - half, y - half], [x + half, y - half],
            [x + half, y + half], [x - half, y + half]]


class WhereInTheYard(unittest.TestCase):

    def test_front_and_back_when_the_street_side_is_known(self):
        self.assertEqual(tl.position_words(0, -14, BOX, SOUTH), "at the front")
        self.assertEqual(tl.position_words(0, 14, BOX, SOUTH), "at the back")
        # The street to the north turns them round.
        self.assertEqual(tl.position_words(0, 14, BOX, 0.0), "at the front")

    def test_beside_the_house_it_says_which_side(self):
        self.assertEqual(tl.position_words(6, 0, BOX, SOUTH), "on the east side")
        self.assertEqual(tl.position_words(-6, 0, BOX, SOUTH), "on the west side")

    def test_the_compass_when_the_street_side_is_only_assumed(self):
        """V3.45's rule for drawing the street: never say as fact what the
        Overview says is taken to be."""
        self.assertEqual(tl.position_words(0, -14, BOX), "on the south side")
        self.assertEqual(tl.position_words(6, 14, BOX),
                         "in the north-east corner")
        for words in (tl.position_words(0, -14, BOX),
                      tl.position_words(6, 14, BOX)):
            self.assertNotIn("front", words)
            self.assertNotIn("back", words)

    def test_the_middle(self):
        self.assertEqual(tl.position_words(0.5, 1.0, BOX, SOUTH),
                         "in the middle of the yard")

    def test_no_yard_no_words(self):
        self.assertEqual(tl.position_words(0, 0, None), "")


class WhatAPlaceIsCalled(unittest.TestCase):

    SURFACES = [
        {"kind": "lawn", "ring": _square(0, 0, 18), "base": True},
        {"kind": "bed", "ring": _square(0, -14)},
        {"kind": "bed", "ring": _square(-5, 14)},
        {"kind": "bed", "ring": _square(5, 12)},
        {"kind": "mulch", "ring": _square(6, 0), "label": "Rain garden"},
        {"kind": "path", "ring": _square(0, -14, 0.5)},
    ]

    def test_the_drawn_area_a_spot_is_in_and_never_the_outlines_lawn(self):
        self.assertEqual(tl.place_of(1.5, -14, self.SURFACES), 1)
        self.assertIsNone(tl.place_of(0, 5, self.SURFACES))

    def test_the_topmost_area_wins(self):
        """A path across a bed: a plant on the path is on the path."""
        self.assertEqual(tl.place_of(0.2, -14, self.SURFACES), 5)

    def test_its_words(self):
        words = [tl.place_words(i, self.SURFACES, BOX, SOUTH, True)
                 for i in (1, 2, None)]
        self.assertEqual(words, ["the garden bed at the front",
                                 "the garden bed at the back",
                                 "the rest of the yard"])
        self.assertEqual(
            tl.place_words(None, self.SURFACES[:1], BOX, SOUTH, False),
            "the yard")

    def test_a_persons_own_name_is_used(self):
        self.assertEqual(
            tl.place_words(4, self.SURFACES, BOX, SOUTH, True),
            "the mulched area “Rain garden”")

    def test_a_label_that_is_only_the_type_is_not_a_name(self):
        surfaces = [{"kind": "bed", "ring": _square(0, -14),
                     "label": "Garden Bed"}]
        self.assertEqual(tl.place_words(0, surfaces, BOX, SOUTH, True),
                         "the garden bed at the front")

    def test_two_beds_with_the_same_words_are_told_apart(self):
        wheres = {i: tl.place_words(i, self.SURFACES, BOX, SOUTH, True)
                  for i in (1, 2, 3)}
        self.assertEqual(wheres[2], wheres[3])
        apart = tl._tell_apart(wheres, self.SURFACES)
        self.assertEqual(apart[1], "the garden bed at the front")
        self.assertEqual(apart[2],
                         "the garden bed at the back (the west one)")
        self.assertEqual(apart[3],
                         "the garden bed at the back (the east one)")

    def test_every_kind_of_surface_has_words(self):
        self.assertEqual(set(tl.PLACE_WORDS), set(scene_site.KINDS))


class WhatShadesThem(unittest.TestCase):

    HOUSE = _square(0, 0, 5)
    BUILDINGS = [{"ring": HOUSE, "kind": "building"},
                 {"ring": _square(6, 14, 3), "kind": "building"},
                 {"ring": _square(20, 0, 5), "kind": "building"},
                 {"ring": _square(-5, 10, 2), "kind": "canopy"}]
    OUTLINE = _square(0, 0, 18)
    PLANTS = [{"existing": True, "x": -3.0, "y": -20.0,
               "foliage_type": "deciduous"},
              {"existing": True, "x": 2.0, "y": 15.0,
               "foliage_type": "evergreen"}]

    def _words(self, shader):
        return tl.shader_words(shader, self.PLANTS, self.BUILDINGS,
                               self.OUTLINE, self.HOUSE)

    def test_the_house_a_building_in_the_yard_and_next_door(self):
        static = {"kind": "static", "is_tree": False}
        self.assertEqual(self._words(dict(static, x=0, y=0)), "the house")
        self.assertEqual(self._words(dict(static, x=6, y=14)),
                         "a building in the yard")
        self.assertEqual(self._words(dict(static, x=20, y=0)),
                         "the building next door")

    def test_trees_already_here(self):
        tree = {"kind": "static", "is_tree": True}
        self.assertEqual(self._words(dict(tree, x=2, y=15)),
                         "the evergreen tree already here")
        self.assertEqual(self._words(dict(tree, x=-3, y=-20)),
                         "the tree already here")

    def test_a_crown_drawn_on_the_map(self):
        self.assertEqual(
            self._words({"kind": "static", "is_tree": True, "x": -5, "y": 10}),
            "the tree drawn on the map")

    def test_a_tree_the_plan_planted(self):
        self.assertEqual(
            self._words({"kind": "plant", "common_name": "Paper Birch",
                         "x": 0, "y": 0}), "the Paper Birch in this plan")

    def test_nothing(self):
        self.assertEqual(self._words(None), "")


class _Engine:
    """The shade model, as far as the notes ask it."""

    def __init__(self, shaders):
        self.shaders = shaders
        self.asked = []

    def death_year(self, index, year):
        return 3

    def main_shader(self, index, year):
        self.asked.append((index, year))
        return self.shaders.get(index)


def _p(name, x, y, **more):
    return dict({"plant_id": 1, "common_name": name, "x": x, "y": y}, **more)


class TheNotes(unittest.TestCase):

    SURFACES = WhatAPlaceIsCalled.SURFACES
    HOUSE = _square(0, 0, 5)
    BUILDINGS = [{"ring": HOUSE, "kind": "building"}]
    BY_THE_HOUSE = {"kind": "static", "is_tree": False, "x": 0, "y": 0}

    def _notes(self, placed, engine=None, plants=None, year=5):
        return tl.notes(
            year=year, when_words="the fifth summer", engine=engine,
            placed=dict(enumerate(placed)), plants=plants or list(placed),
            surfaces=self.SURFACES, buildings=self.BUILDINGS,
            boundary=_square(0, 0, 18), focus=None, street_bearing=SOUTH,
            house=self.HOUSE)

    def test_one_note_per_place_with_how_many_of_how_many(self):
        placed = ([_p("Wild Strawberry", 0.5 * i - 1, -13.5, gone="shade")
                   for i in range(3)]
                  + [_p("Smooth Aster", 1.5, -15.0, gone="shade")]
                  + [_p("Blue Grama", -1.5, -15.5)] * 4
                  + [_p("Blue Grama", -1.0, -12.5, health_state="declining")])
        got = self._notes(placed, _Engine({i: self.BY_THE_HOUSE
                                           for i in range(4)}))
        self.assertEqual(got["when"], "the fifth summer")
        self.assertEqual(len(got["notes"]), 1)
        note = got["notes"][0]
        self.assertEqual(
            note["text"],
            "4 of the 9 plants in the garden bed at the front are shaded out "
            "by the fifth summer, by the house. 1 more is struggling in the "
            "shade.")
        self.assertEqual((note["lost"], note["of"], note["struggling"]),
                         (4, 9, 1))
        self.assertEqual(note["by"], "the house")
        self.assertEqual(note["plants"],
                         [["Wild Strawberry", 3], ["Smooth Aster", 1]])
        self.assertEqual(note["kinds"], "Wild Strawberry (3) and Smooth Aster")
        self.assertEqual(len(note["spots"]), 4)
        self.assertIn([1.5, -15.0], note["spots"])

    def test_the_cause_is_asked_for_the_year_the_plant_died(self):
        engine = _Engine({0: self.BY_THE_HOUSE})
        self._notes([_p("A", 1.5, -14.0, gone="shade")], engine)
        self.assertEqual(engine.asked, [(0, 3)])

    def test_most_of_them_and_more_than_one(self):
        other = {"kind": "plant", "common_name": "Paper Birch", "x": 1, "y": 1}
        lost = [_p("A", 1.5, -13.0 - 0.3 * i, gone="shade") for i in range(4)]
        mostly = self._notes(lost, _Engine(
            {0: self.BY_THE_HOUSE, 1: self.BY_THE_HOUSE, 2: self.BY_THE_HOUSE,
             3: other}))
        self.assertIn("most of them by the house.", mostly["notes"][0]["text"])
        mixed = self._notes(lost[:3], _Engine(
            {0: self.BY_THE_HOUSE, 1: other,
             2: {"kind": "static", "is_tree": True, "x": 9, "y": 9}}))
        self.assertIn("by more than one tree or building.",
                      mixed["notes"][0]["text"])

    def test_one_plant_and_all_of_them(self):
        one = self._notes([_p("A", 1.5, -14.0, gone="shade")])
        self.assertTrue(one["notes"][0]["text"].startswith(
            "The one plant in the garden bed at the front is shaded out"))
        every = self._notes([_p("A", 1.5, -14.0, gone="shade"),
                             _p("B", 1.6, -15.0, gone="shade")])
        self.assertTrue(every["notes"][0]["text"].startswith(
            "All 2 plants in the garden bed at the front are shaded out"))

    def test_a_bed_keeps_its_name_whichever_beds_lost_plants(self):
        """Two beds at the back and losses in one: it is still told apart
        from the other, or "the garden bed at the back" would be one bed in
        the fifth summer and another in the tenth."""
        got = self._notes([_p("A", -5, 14, gone="shade"), _p("B", 5, 12)])
        self.assertEqual(got["notes"][0]["where"],
                         "the garden bed at the back (the west one)")

    def test_places_are_listed_most_lost_first(self):
        placed = ([_p("A", -5, 14, gone="shade")]
                  + [_p("B", 1.5, -14.0 - 0.2 * i, gone="shade")
                     for i in range(3)]
                  + [_p("C", 0, 6, gone="shade")] * 2)
        wheres = [n["where"] for n in self._notes(placed)["notes"]]
        self.assertEqual(wheres, ["the garden bed at the front",
                                  "the rest of the yard",
                                  "the garden bed at the back (the west one)"])

    def test_short_lived_kinds_are_said_as_how_they_grow(self):
        got = self._notes([_p("Fireweed", 0, 6, gone="short_lived")] * 2
                          + [_p("Blue Grama", 0, 7)])
        self.assertEqual([n["kind"] for n in got["notes"]], ["short_lived"])
        text = got["notes"][0]["text"]
        self.assertIn("2 plants of kinds that fill in first and then give way",
                      text)
        self.assertIn("not a fault in the plan", text)
        self.assertNotIn("shaded", text)

    def test_gaps_the_plans_own_plants_have_taken(self):
        placed = [_p("A", 1.5, -14.0, gone="shade")]
        seeded = [_p("Wild Strawberry", 1.5, -14.0, recruit=True)]
        got = self._notes(placed, plants=placed + seeded)
        self.assertEqual([n["kind"] for n in got["notes"]],
                         ["shade", "self_seeded"])
        self.assertEqual(got["notes"][1]["count"], 1)
        self.assertEqual(got["notes"][1]["spots"], [[1.5, -14.0]])

    def test_nothing_lost_nothing_said(self):
        self.assertIsNone(self._notes([_p("A", 0, 6), _p("B", 1, 6)]))

    def test_fully_grown_is_not_a_year_anything_is_lost_in(self):
        self.assertIsNone(self._notes([_p("A", 0, 6, gone="shade")], year=0))

    def test_it_says_it_is_an_estimate_and_what_to_do(self):
        got = self._notes([_p("A", 1.5, -14.0, gone="shade")])
        self.assertIn("estimate", got["about"])
        self.assertIn("not a forecast", got["about"])
        self.assertIn("Swap", got["about"])


class TheKindsInWords(unittest.TestCase):

    def test_counts_only_where_there_is_more_than_one(self):
        self.assertEqual(tl.kinds_words([["A", 3], ["B", 1]]), "A (3) and B")
        self.assertEqual(tl.kinds_words([["A", 1]]), "A")
        self.assertEqual(tl.kinds_words([]), "")

    def test_a_long_list_is_cut_and_says_how_many_more(self):
        kinds = [[f"Plant {i}", 9 - i] for i in range(8)]
        words = tl.kinds_words(kinds)
        self.assertIn("Plant 4 (5)", words)
        self.assertNotIn("Plant 5", words)
        self.assertTrue(words.endswith("and 3 other kinds"), words)


# ── the scene's notes are the scene's own losses ─────────────────────────────

class TheSceneCarriesThem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from tests import test_yard_render as yard
        cls.yard = yard
        cls.scene = build_scene(yard._yard(), year=yard.YEAR,
                                get_plant=yard._PLANTS.get, wind=False,
                                when=datetime(2025, 7, 21, 13, 0))

    def test_every_plant_lost_to_shade_is_in_exactly_one_note(self):
        lost = [p for p in self.scene["plants"] if p.get("gone") == "shade"]
        self.assertTrue(lost, "the fixture lost nothing to shade")
        notes = [n for n in self.scene["timeline_notes"]["notes"]
                 if n["kind"] == "shade"]
        self.assertEqual(sum(n["lost"] for n in notes), len(lost))
        spots = sorted(tuple(s) for n in notes for s in n["spots"])
        self.assertEqual(spots, sorted((p["x"], p["y"]) for p in lost))

    def test_the_place_and_the_cause_are_the_yards(self):
        note = next(n for n in self.scene["timeline_notes"]["notes"]
                    if n["kind"] == "shade")
        self.assertEqual(note["where"], "the garden bed at the front")
        self.assertEqual(note["by"], "the Aspen in this plan")
        self.assertIn("by the twenty-fifth summer", note["text"])
        self.assertEqual(note["plants"][0][0], "Sun forb")

    def test_the_short_lived_are_counted_as_the_line_counts_them(self):
        lived = [p for p in self.scene["plants"]
                 if p.get("gone") == "short_lived"]
        note = next(n for n in self.scene["timeline_notes"]["notes"]
                    if n["kind"] == "short_lived")
        self.assertEqual(note["lost"], len(lived))

    def test_fully_grown_and_the_first_summer_say_nothing(self):
        for year in (0, 1):
            scene = build_scene(self.yard._yard(), year=year,
                                get_plant=self.yard._PLANTS.get, wind=False)
            self.assertIsNone(scene["timeline_notes"], year)

    def test_the_scene_still_serialises(self):
        import json
        json.dumps(self.scene["timeline_notes"])

    def test_a_kept_scene_gives_the_same_notes_and_a_new_bed_new_words(self):
        """The notes are kept per year while the design is what it was: a bed
        drawn round the lost plants must change what they say."""
        memo = {}
        project = self.yard._yard()
        project["features"] = [
            f for f in project["features"]
            if (f.get("properties") or {}).get("shape_type") != "Garden Bed"]
        kw = dict(year=self.yard.YEAR, get_plant=self.yard._PLANTS.get,
                  wind=False, memo=memo)
        first = build_scene(project, **kw)["timeline_notes"]
        again = build_scene(project, **kw)["timeline_notes"]
        self.assertEqual(first, again)
        where = next(n for n in first["notes"] if n["kind"] == "shade")["where"]
        self.assertEqual(where, "the rest of the yard")
        project["features"].append(self.yard.DRAWN[0])        # the bed, back
        third = build_scene(project, **kw)["timeline_notes"]
        self.assertEqual(
            next(n for n in third["notes"] if n["kind"] == "shade")["where"],
            "the garden bed at the front")


if __name__ == "__main__":
    unittest.main()
