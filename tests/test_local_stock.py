"""
tests/test_local_stock.py — availability from the region's nurseries' stock
(V3.25, ``src/local_stock.py``).

The owner: levels "based on actual stock that is available at these local
retailers"; yarrow, prairie crocus, wild bergamot and giant hyssop common,
harebell and prairie sage now and then; a restoration plant never in the most
common tier; a Calgary nursery's list counts only for Edmonton's natives.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import local_stock as ls  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVES = {"A a", "B b", "C c", "D d", "E e"}


def _list(supplier, species, seen="2026-05", form="plants"):
    return {"supplier": supplier, "seen": seen, "form": form,
            "source": "test", "species": list(species)}


class TheRules(unittest.TestCase):

    def test_two_suppliers_most_lists_is_common(self):
        doc = {"lists": [_list("X", ["A a"]), _list("Y", ["A a"])]}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "common")

    def test_one_supplier_is_sometimes(self):
        doc = {"lists": [_list("X", ["A a"])]}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "sometimes")

    def test_once_in_a_while_is_sometimes(self):
        """On one of a supplier's three lists is not regular there."""
        doc = {"lists": [_list("X", ["A a"], "2024-05"), _list("X", [], "2025-05"),
                         _list("X", [], "2026-05"), _list("Y", ["A a"])]}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "sometimes")

    def test_seed_only(self):
        doc = {"lists": [_list("X", ["A a"], form="seed")]}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "seed")

    def test_absent_is_unchecked_until_enough_lists(self):
        """P9: two suppliers' lists missing a plant say little; three say it is
        hard to find."""
        two = {"lists": [_list("X", ["A a"]), _list("Y", ["A a"])]}
        self.assertEqual(ls.derive(two, NATIVES)["B b"], "unchecked")
        three = {"lists": two["lists"] + [_list("Z", ["A a"])]}
        self.assertEqual(ls.derive(three, NATIVES)["B b"], "hard")

    def test_a_restoration_plant_is_never_common(self):
        doc = {"lists": [_list("X", ["A a"]), _list("Y", ["A a"])],
               "rulings": {"B b": {"tier": "common", "on": "2026-10-16"}}}
        got = ls.derive(doc, NATIVES, restoration={"A a", "B b", "C c"})
        self.assertEqual(got["A a"], "sometimes")
        self.assertEqual(got["B b"], "sometimes")
        self.assertEqual(got["C c"], "hard", "no list: hard, not unchecked")

    def test_the_owner_wins(self):
        doc = {"lists": [_list("X", ["A a"]), _list("Y", ["A a"])],
               "rulings": {"A a": {"tier": "sometimes", "on": "2026-10-16"}}}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "sometimes")

    def test_only_the_regions_natives_are_ranked(self):
        """A Calgary nursery's foothills plant gets no Edmonton tier."""
        doc = {"lists": [_list("X", ["Z z"]), _list("Y", ["Z z"])]}
        self.assertNotIn("Z z", ls.derive(doc, NATIVES))


class TheShippedStock(unittest.TestCase):

    def setUp(self):
        from src import region
        self.region = region.default()
        with open(ls.path(self.region.key), encoding="utf-8") as fh:
            self.doc = json.load(fh)
        with open(os.path.join(ROOT, "data", "plants_master.json"),
                  encoding="utf-8") as fh:
            self.catalogue = {p["scientific_name"] for p in json.load(fh)}

    def test_it_validates(self):
        self.assertEqual(ls.validate(self.doc, self.region.nurseries,
                                     self.catalogue), [])

    def test_the_owners_six(self):
        for name in ("Achillea borealis", "Pulsatilla nuttalliana",
                     "Monarda fistulosa", "Agastache foeniculum"):
            self.assertEqual(ls.tier(name), "common", name)
        for name in ("Campanula rotundifolia", "Artemisia ludoviciana"):
            self.assertEqual(ls.tier(name), "sometimes", name)

    def test_a_list_from_another_supplier_is_refused(self):
        doc = {"lists": [_list("Big Box Co", ["Achillea borealis"])]}
        self.assertTrue(ls.validate(doc, self.region.nurseries))

    def test_a_ruling_carries_no_reason(self):
        doc = {"rulings": {"Achillea borealis": {"tier": "common",
                                                 "reason": "x"}}}
        self.assertTrue(ls.validate(doc))


class TheAppReadsIt(unittest.TestCase):

    def tearDown(self):
        ls.set_document(None)

    def test_the_filter_and_easy_to_find(self):
        from src.db.plants import search_plants
        names = {p["scientific_name"] for p in search_plants(stock_in=["common"])}
        self.assertIn("Monarda fistulosa", names)
        self.assertNotIn("Campanula rotundifolia", names)
        easy = {p["scientific_name"] for p in search_plants(common_only=True)}
        self.assertIn("Campanula rotundifolia", easy)

    def test_the_filter_facet_reads_the_tiers(self):
        from src import plant_filters as pf
        f = next(f for f in pf.FACETS if f.key == "availability")
        self.assertEqual(f.param, "stock_in")
        self.assertEqual(set(f.values), set(ls.TIERS))

    def test_the_plant_page_sentence(self):
        self.assertIn("Common at Edmonton",
                      ls.clause("Monarda fistulosa"))
        self.assertIn("check before you go",
                      ls.clause("Campanula rotundifolia"))
        self.assertEqual(ls.clause("Not a plant"), "")

    def test_the_order_file_names_the_listing_supplier(self):
        from src import order_file
        key = __import__("src.region", fromlist=["x"]).default().key
        ls.set_document(key, {"lists": [_list("Arnica Wildflowers",
                                              ["Monarda fistulosa"])]})
        listed = order_file._listed_by(53.52, -113.52)
        self.assertEqual(listed("Monarda fistulosa"),
                         "Arnica Wildflowers (2026-05)")
        self.assertEqual(order_file._listed_by(50.45, -104.6)(
            "Monarda fistulosa"), "", "outside the pack, no local supplier")


class ReadingANurseryList(unittest.TestCase):
    """``src/stock_lists`` and ``scripts/merge_stock.py``."""

    def setUp(self):
        from src import stock_lists
        with open(os.path.join(ROOT, "data", "plants_master.json"),
                  encoding="utf-8") as fh:
            self.table = stock_lists.name_table(json.load(fh))
        self.match = stock_lists.match

    def test_names_old_names_and_noise(self):
        found, unread = self.match(
            "Wild Bergamot (Monarda fistulosa) 1 gal $12\n"
            "Yarrow, Common - Achillea millefolium\n"
            "Pasque flower\nWild Blue Flax\nHosta 'Blue Angel'\n", self.table)
        self.assertEqual(found, ["Monarda fistulosa", "Achillea borealis",
                                 "Pulsatilla nuttalliana", "Linum lewisii"])
        self.assertEqual(unread, ["Hosta 'Blue Angel'"])

    def test_merge_adds_replaces_and_takes_back(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import merge_stock
        doc = {"lists": [_list("Arnica Wildflowers", ["A a"])],
               "rulings": {"Achillea borealis": {"tier": "common", "on": "x"}}}
        review = {"lists": [{"supplier": "Arnica Wildflowers",
                             "seen": "2026-05", "form": "plants",
                             "text": "Harebell\nGiant Hyssop"}],
                  "rulings": {"Achillea borealis": {"tier": ""},
                              "Monarda fistulosa": {"tier": "common",
                                                    "on": "2026-10-16"}}}
        new, _report = merge_stock.merge(doc, review)
        self.assertEqual(len(new["lists"]), 1, "same supplier and date: replaced")
        self.assertEqual(new["lists"][0]["species"],
                         ["Campanula rotundifolia", "Agastache foeniculum"])
        self.assertNotIn("Achillea borealis", new["rulings"])
        self.assertEqual(new["rulings"]["Monarda fistulosa"]["tier"], "common")


class TheReviewPage(unittest.TestCase):

    def test_it_builds_with_every_local_native(self):
        from src import native_here, region
        from tools.stock_review import build
        data = build.page_data()
        self.assertEqual(len(data["species"]),
                         len(native_here.native_names(region.default().key)))
        self.assertEqual(data["region"]["nurseries"],
                         list(region.default().nurseries))
        page = build.render(data)
        self.assertNotIn("/*__DATA__*/null", page)
        self.assertIn("<title>", page)


if __name__ == "__main__":
    unittest.main()
