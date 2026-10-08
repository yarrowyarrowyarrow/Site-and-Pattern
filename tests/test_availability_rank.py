"""
tests/test_availability_rank.py — where a plant can actually be bought (V3.14).

The owner: "most can only be gotten at a native plant specialist and even then
many are too rare to be found there." ``availability_class`` had come from name
keywords, so Alpine Aster and Skunk Currant read garden-centre stock and only
orchids, gentians, the wood lily and the sundew read rare.
``scripts/rank_availability.py`` owns the field now, with a reason per rare
plant; the generator and the community library rank by it.
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def _script():
    spec = importlib.util.spec_from_file_location(
        "rank_availability", os.path.join(_ROOT, "scripts",
                                          "rank_availability.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalogue() -> list:
    with open(os.path.join(_ROOT, "data", "plants_master.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


class TestTheRules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ra = _script()
        cls.records = cls.ra._records()
        cls.by_name = {p["common_name"]: p for p in _catalogue()}

    def tier(self, name):
        return self.ra.rank(self.by_name[name], self.records)[0]

    def test_the_trade_lists(self):
        self.assertEqual(self.tier("Saskatoon Berry"), "big_box")
        self.assertEqual(self.tier("Blanketflower"), "garden_centre")
        self.assertEqual(self.tier("Alpine Aster"), "garden_centre")

    def test_a_name_keyword_no_longer_makes_garden_centre_stock(self):
        for name in ("Skunk Currant", "Marsh Cinquefoil", "Willow Aster",
                     "Sticky Goldenrod"):
            self.assertNotIn(self.tier(name), ("garden_centre", "big_box"),
                             name)

    def test_what_is_rarely_sold_and_why(self):
        for name, why in (("Moss Campion", "mountains"),
                          ("Common Paintbrush", "hemiparasite"),
                          ("Sago Pondweed", "water plant"),
                          ("Labrador Tea", "bog"),
                          ("Yellow Lady's Slipper", "orchid")):
            tier, note = self.ra.rank(self.by_name[name], self.records)
            self.assertEqual(tier, "rare", name)
            self.assertIn(why, note, name)

    def test_foothills_plants_the_nurseries_grow_are_not_rare(self):
        self.assertEqual(self.tier("Yellow Columbine"), "native_specialist")
        self.assertEqual(self.tier("Pearly Everlasting"), "native_specialist")

    def test_grasses_sedges_and_rushes_are_seed_or_plug(self):
        for p in _catalogue():
            if p["plant_type"] in ("sedge", "rush"):
                self.assertEqual(self.tier(p["common_name"]), "seed_or_plug")

    def test_every_listed_name_is_in_the_catalogue(self):
        """A misspelt name in a list is a rule that silently does nothing."""
        names = {p["scientific_name"].strip() for p in _catalogue()}
        listed = (self.ra.BIG_BOX | self.ra.GARDEN_CENTRE
                  | self.ra.SEED_OR_PLUG | self.ra.NURSERY_GROWN
                  | set(self.ra.OWNER)
                  | set().union(*self.ra.RARE.values()))
        self.assertEqual(sorted(listed - names), [])

    def test_the_note_is_replaced_never_stacked(self):
        note = self.ra._note
        once = note("Estimate (herb default); AB retail as of 2026",
                    "Rarely sold: a bog plant.")
        self.assertEqual(note(once, "Rarely sold: a bog plant."), once)
        self.assertEqual(note(once, ""),
                         "Estimate (herb default); AB retail as of 2026")


class TestTheShippedData(unittest.TestCase):
    """The data is what the script computes: a tier edited by hand belongs in
    ``OWNER``, where it says whose it is."""

    def test_the_catalogue_matches_the_script(self):
        ra = _script()
        records = ra._records()
        for p in _catalogue():
            tier, why = ra.rank(p, records)
            self.assertEqual(p["availability_class"], tier, p["common_name"])
            if why:
                self.assertTrue(p["sourcing_notes"].endswith(why),
                                p["common_name"])

    def test_most_are_native_nursery_plants_and_many_rare(self):
        """The owner's two claims, as counts."""
        tiers = [p["availability_class"] for p in _catalogue()]
        sold_widely = sum(t in ("garden_centre", "big_box") for t in tiers)
        self.assertLess(sold_widely, tiers.count("native_specialist") / 4)
        self.assertGreater(tiers.count("rare"), 50)


class TestTheyRankDesigns(unittest.TestCase):
    """The generator and the library read the tiers (V3.14)."""

    def test_ease(self):
        from src.sourcing import ease, hard_to_find
        self.assertEqual(ease({"availability_class": "big_box"}), 2)
        self.assertEqual(ease({"availability_class": "native_specialist"}), 1)
        self.assertEqual(ease({"availability_class": "rare"}), 0)
        self.assertEqual(ease({}), 1, "unrecorded is not rare")
        self.assertTrue(hard_to_find({"availability_class": "rare"}))

    def test_the_offline_generator_waits_on_a_rare_plant(self):
        """A rare keystone host ranks after a plain pollinator people can buy."""
        from src.llm_design import _rank_offline_plants
        rare = {"id": 1, "plant_type": "wildflower", "common_name": "R",
                "permaculture_uses": "keystone_species,host_plant",
                "availability_class": "rare"}
        plain = {"id": 2, "plant_type": "wildflower", "common_name": "P",
                 "permaculture_uses": "pollinator",
                 "availability_class": "native_specialist"}
        order = [p["id"] for p in _rank_offline_plants([rare, plain])]
        self.assertEqual(order, [2, 1])

    def test_among_equals_the_easier_to_buy_comes_first(self):
        from src.llm_design import _rank_offline_plants
        nursery = {"id": 1, "plant_type": "shrub", "common_name": "N",
                   "permaculture_uses": "bird_food",
                   "availability_class": "native_specialist"}
        centre = {"id": 2, "plant_type": "shrub", "common_name": "G",
                  "permaculture_uses": "bird_food",
                  "availability_class": "garden_centre"}
        order = [p["id"] for p in _rank_offline_plants([nursery, centre])]
        self.assertEqual(order, [2, 1])

    def test_the_design_reviews_repairs_reach_for_a_rare_plant_last(self):
        from src.llm_design import _site_scoped_query
        rows = [{"id": 1, "scientific_name": "A a",
                 "availability_class": "rare"},
                {"id": 2, "scientific_name": "B b",
                 "availability_class": "native_specialist"}]
        scoped = _site_scoped_query(lambda **_f: list(rows), {})
        self.assertEqual([r["id"] for r in scoped()], [2, 1])

    def test_the_budget_goal_finds_the_easy_communities(self):
        from src.design_goals import community_name_hints
        self.assertIn("Easy", community_name_hints(["low_cost"]))


class TestTheLibrary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import src.db.plants as plants
        cls._saved = (plants._DATA_DIR, plants._DB_PATH)
        d = tempfile.mkdtemp(prefix="availability_rank_")
        plants._DATA_DIR, plants._DB_PATH = d, os.path.join(d, "t.db")
        plants.init_db()
        from src.db import polycultures
        cls.P = polycultures
        cls.index = polycultures.get_library_index()
        cls.by_name = {e["name"]: cid for cid, e in cls.index.items()}

    @classmethod
    def tearDownClass(cls):
        import src.db.plants as plants
        plants._DATA_DIR, plants._DB_PATH = cls._saved

    def test_the_easy_communities_hold_nothing_rarely_sold(self):
        easy = [n for n in self.by_name if n.startswith("Easy ")]
        self.assertEqual(len(easy), 5)
        for name in easy:
            entry = self.index[self.by_name[name]]
            self.assertEqual(entry["hard_to_find"], [], name)
            self.assertEqual(entry["not_around"]["edmonton"], [], name)
            self.assertIn("aspen_parkland", entry["regions"], name)

    def test_a_row_says_how_many_are_hard_to_find(self):
        try:
            from src.polyculture_panel import community_facts
        except ImportError as exc:                            # noqa: BLE001
            self.skipTest(str(exc))
        hard = next(e for e in self.index.values() if e["hard_to_find"])
        self.assertIn(f"{len(hard['hard_to_find'])} hard to find",
                      community_facts(hard))

    def test_a_design_names_what_nobody_sells(self):
        import src.db.plants as plants
        from src.llm_design import _note_hard_to_find
        conn = plants.get_connection()
        try:
            rare, common = (conn.execute(
                "SELECT id, common_name FROM plants WHERE availability_class=? "
                "ORDER BY id LIMIT 1", (tier,)).fetchone()
                for tier in ("rare", "big_box"))
        finally:
            conn.close()

        class Project:
            def __init__(self, ids):
                self.placed_plants = [{"plant_id": i[0], "common_name": i[1]}
                                      for i in ids]
                self.doc = {}

            def as_dict(self):
                return self.doc

        with_rare = Project([rare, common])
        _note_hard_to_find(with_rare)
        notes = with_rare.doc["properties"]["generation_warnings"]
        self.assertEqual(len(notes), 1)
        self.assertIn(rare[1], notes[0])
        self.assertNotIn(common[1], notes[0])
        without = Project([common])
        _note_hard_to_find(without)
        self.assertNotIn("properties", without.doc)

    def test_easiest_to_buy_sorts_them_first(self):
        top = [cid for cid, e in self.index.items() if e["parent_id"] is None]
        ordered = self.P.sort_community_ids(self.index, top, "easiest")
        shares = [len(self.index[i]["hard_to_find"])
                  / max(1, self.index[i]["member_count"]) for i in ordered]
        self.assertEqual(shares, sorted(shares))
        self.assertEqual(shares[0], 0)


if __name__ == "__main__":
    unittest.main()
