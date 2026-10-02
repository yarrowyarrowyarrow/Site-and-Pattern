"""
tests/test_what_it_feeds.py — Design › Food's arithmetic (V3.08).

The owner merged Analysis › Bees and Planning's Wildlife and Harvest calendars
into one "what it feeds" page: any animal, not only bees, and "clear and
distinct what is human forage and what is animal forage". ``src/what_it_feeds``
is that page's arithmetic, over the edges layer and the real catalogue.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="sp_what_it_feeds_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "what_it_feeds.db")

from src import what_it_feeds as feeds  # noqa: E402


class TestTheWords(unittest.TestCase):
    """No database: how a month, a group and a line read."""

    def test_months_read_as_runs(self):
        self.assertEqual(feeds.span([7, 8, 10]), "Jul–Aug, Oct")
        self.assertEqual(feeds.span([5]), "May")
        self.assertEqual(feeds.span([]), "")
        self.assertEqual(feeds.span([9, 8, 8, 7]), "Jul–Sep")

    def test_groups_count_in_plain_words(self):
        self.assertEqual(feeds.group_words("bee", 1), "1 bee")
        self.assertEqual(feeds.group_words("lepidoptera", 3),
                         "3 butterflies and moths")
        self.assertEqual(feeds.group_words("bird", 2), "2 birds")

    def test_a_planted_species_line(self):
        line = feeds.eaters_line({"animals": {"bird": 1, "bee": 2},
                                  "bloom": [7, 8], "fruit": [9]})
        # Groups in the page's order (bees first), whatever order they came.
        self.assertEqual(line, "feeds 3: 2 bees, 1 bird · flowers Jul–Aug · "
                               "fruit Sep")

    def test_nothing_recorded_says_so_rather_than_nothing(self):
        """P9: an empty line would read as "feeds nothing", which the
        catalogue cannot know."""
        self.assertEqual(feeds.eaters_line({}), "no animal recorded")

    def test_when_an_animal_eats_is_read_off_the_plant(self):
        bloom, fruit = [6, 7], [9]
        self.assertEqual(feeds.months_for("nectar", bloom, fruit), {6, 7})
        self.assertEqual(feeds.months_for("seed_food", bloom, fruit), {9})
        self.assertEqual(feeds.months_for("larval_host", bloom, fruit,
                                          "lepidoptera"),
                         set(feeds.LEAF_MONTHS))
        # Shelter is not food, so it adds no month.
        self.assertEqual(feeds.months_for("nesting", bloom, fruit), set())

    def test_a_larval_host_is_a_caterpillar_host_only_for_a_caterpillar(self):
        """The catalogue's larval_host edges include bees (GloBI's hostOf, a
        specimen's flower) and beetles; "caterpillar host" was wrong for both
        when the page first called every one that."""
        self.assertEqual(feeds.kind_words("larval_host", "lepidoptera"),
                         "caterpillar host")
        self.assertEqual(feeds.kind_words("larval_host", "bee"), "host plant")
        self.assertEqual(feeds.kind_words("larval_host", "other_insect"),
                         "larval host")
        # A bee's host plant is a flower record: its months are the bloom's.
        self.assertEqual(feeds.months_for("larval_host", [6], [9], "bee"), {6})
        self.assertEqual(feeds.kind_words("nectar", "bee"), "nectar")


class TestAgainstTheCatalogue(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod.init_db()
        import src.permadesign_api as api
        api._DB_READY = True
        cls.rows = {r["common_name"]: r for r in api.query_plants()}
        cls.ids = [cls.rows[n]["id"] for n in
                   ("Wild Bergamot", "Showy Milkweed", "Chokecherry")]

    def test_every_animal_fed_is_listed_once_most_plants_first(self):
        fed = feeds.animals_fed(self.ids)
        self.assertGreater(len(fed), 50)
        self.assertEqual(len({a["fauna_id"] for a in fed}), len(fed))
        counts = [len(a["plants"]) for a in fed]
        self.assertEqual(counts, sorted(counts, reverse=True))
        allowed = set(feeds.FOOD_KINDS) | set(feeds.SHELTER_KINDS)
        for a in fed:
            self.assertLessEqual(set(a["plants"]), set(self.ids))
            kinds = {k for ks in a["plants"].values() for k in ks}
            self.assertLessEqual(kinds, allowed)
            self.assertEqual(a["food"], bool(kinds & set(feeds.FOOD_KINDS)))

    def test_a_community_counts_each_animal_once(self):
        together = feeds.together(self.ids)
        fed = [a for a in feeds.animals_fed(self.ids) if a["food"]]
        self.assertEqual(sum(together["animals"].values()), len(fed))
        apart = feeds.plant_food(self.ids)
        self.assertLess(sum(together["animals"].values()),
                        sum(sum(p["animals"].values()) for p in apart.values()),
                        "a shared animal was counted for every plant")
        self.assertEqual(set(together["bloom"]),
                         {m for p in apart.values() for m in p["bloom"]})

    def test_one_animal_against_the_design(self):
        fed = feeds.animals_fed(self.ids)
        fid = next(a["fauna_id"] for a in fed if a["taxon"] == "lepidoptera")
        plan = feeds.animal_plan(fid, self.ids, elsewhere=5)
        here = {e["plant_id"] for e in plan["here"]}
        self.assertTrue(here)
        self.assertLessEqual(here, set(self.ids))
        self.assertFalse(here & {e["plant_id"] for e in plan["elsewhere"]})
        self.assertLessEqual(len(plan["elsewhere"]), 5)
        self.assertGreaterEqual(plan["elsewhere_total"], len(plan["elsewhere"]))
        # The gaps are the growing season's months it finds nothing in.
        self.assertFalse(set(plan["gaps"]) & set(plan["months_here"]))
        self.assertLessEqual(set(plan["gaps"]),
                             set(feeds.GROWING_SEASON_MONTHS))
        # Food first among the plants that would also serve it.
        food_first = [any(k in feeds.FOOD_KINDS for k in e["kinds"])
                      for e in plan["elsewhere"]]
        self.assertEqual(food_first, sorted(food_first, reverse=True))

    def test_an_animal_the_design_does_not_feed_is_a_shopping_list(self):
        prairie = [self.rows["Rough Fescue"]["id"]]
        fed_by_chokecherry = {a["fauna_id"] for a in
                              feeds.animals_fed([self.rows["Chokecherry"]["id"]])
                              if a["food"]}
        fed_by_fescue = {a["fauna_id"] for a in feeds.animals_fed(prairie)}
        fid = sorted(fed_by_chokecherry - fed_by_fescue)[0]
        plan = feeds.animal_plan(fid, prairie)
        self.assertEqual(plan["here"], [])
        self.assertEqual(plan["gaps"], [], "no gaps claimed for an animal "
                                           "the design does not serve at all")
        self.assertIn(self.rows["Chokecherry"]["id"],
                      [e["plant_id"] for e in
                       feeds.animal_plan(fid, prairie, elsewhere=500)
                       ["elsewhere"]])

    def test_people_are_kept_apart_from_the_animals(self):
        """The owner: "clear and distinct what is human forage and what is
        animal forage". A plant with nothing edible recorded is never a
        harvest, and the people's entries name the part eaten."""
        fescue = self.rows["Rough Fescue"]["id"]
        year = feeds.month_by_month(self.ids + [fescue])
        people = [entry for m in year["months"] for entry in m["people"]]
        self.assertTrue(people)
        for name, part in people:
            self.assertNotEqual(name, "Rough Fescue")
            self.assertTrue(part)
        self.assertIn("Chokecherry", {name for name, _part in people})
        # A grass flowers for the wind, not for a bee (V2.91, F182).
        for m in year["months"]:
            self.assertNotIn("Rough Fescue", m["pollinators"])

    def test_the_planted_line_for_a_real_plant(self):
        pid = self.rows["Chokecherry"]["id"]
        line = feeds.eaters_line(feeds.plant_food([pid])[pid])
        self.assertRegex(line, r"^feeds \d+: \d+ bees?, ")
        self.assertIn("· flowers ", line)
        self.assertIn("· fruit ", line)


if __name__ == "__main__":
    unittest.main()
