"""
tests/test_local_stock.py — availability from the region's nurseries' stock
(V3.25, ``src/local_stock.py``).

The owner: levels "based on actual stock that is available at these local
retailers"; V3.26: Arnica's listed plants are "available" rather than common,
harebell and prairie sage now and then; a restoration plant never in the most
common tier; a Calgary nursery's list counts only for Edmonton's natives.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir BEFORE importing anything that opens it.
import tempfile  # noqa: E402
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_stock_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
_plants_mod.init_db()

from src import local_stock as ls  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVES = {"A a", "B b", "C c", "D d", "E e"}


def _list(supplier, species, seen="2026-05", form="plants"):
    return {"supplier": supplier, "seen": seen, "form": form,
            "source": "test", "species": list(species)}


class TheRules(unittest.TestCase):
    """V3.26: "These ones at Arnica should be listed as 'available' rather
    than common." The levels say only what a list says."""

    def test_on_any_plant_list_is_available(self):
        doc = {"lists": [_list("X", ["A a"], "2024-05"), _list("X", [], "2026-05")]}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "available")

    def test_seed_only(self):
        doc = {"lists": [_list("X", ["A a"], form="seed")]}
        self.assertEqual(ls.derive(doc, NATIVES)["A a"], "seed")

    def test_absent_is_unlisted_never_hard(self):
        """P9: one nursery's lists missing a plant do not make it hard to
        find."""
        doc = {"lists": [_list(s, ["A a"]) for s in "XYZW"]}
        self.assertEqual(ls.derive(doc, NATIVES)["B b"], "unlisted")

    def test_a_restoration_plant(self):
        """Hard to find when no list carries it; available when one does (the
        owner's Arnica lists carry Arctic Aster)."""
        doc = {"lists": [_list("X", ["A a"])]}
        got = ls.derive(doc, NATIVES, restoration={"A a", "C c"})
        self.assertEqual(got["A a"], "available")
        self.assertEqual(got["C c"], "hard")

    def test_the_owner_wins_and_old_answers_still_read(self):
        doc = {"lists": [_list("X", ["A a"])],
               "rulings": {"A a": {"tier": "hard", "on": "2026-10-16"},
                           "B b": {"tier": "common", "on": "2026-10-16"}}}
        got = ls.derive(doc, NATIVES)
        self.assertEqual(got["A a"], "hard")
        self.assertEqual(got["B b"], "available", "V3.25's 'common'")

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

    def test_the_owners_lists(self):
        """The owner's screenshots (V3.26): Arnica Wildflowers' 3 May, 7 June
        and 30 August 2026 market lists and the Edmonton Native Plant
        Society's 16 August and 12 September 2026 sale lists."""
        seen = sorted((l["supplier"], l["seen"], len(l["species"]))
                      for l in self.doc["lists"])
        self.assertEqual(seen, [
            ("Arnica Wildflowers", "2026-05-03", 24),
            ("Arnica Wildflowers", "2026-06-07", 48),
            ("Arnica Wildflowers", "2026-08-30", 50),
            ("Edmonton Native Plant Society", "2026-08-16", 38),
            ("Edmonton Native Plant Society", "2026-09-12", 15)])
        for name in ("Achillea borealis", "Pulsatilla nuttalliana",
                     "Monarda fistulosa", "Agastache foeniculum",
                     "Campanula rotundifolia", "Artemisia ludoviciana",
                     "Liatris ligulistylis"):
            self.assertEqual(ls.tier(name), "available", name)
        self.assertEqual(ls.counts()["available"], 70)

    def test_each_list_reads_from_its_transcription(self):
        """The file in tools/stock_review/lists/ is the evidence: reading it
        again gives the list on file, so neither drifts."""
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import merge_stock
        for l in self.doc["lists"]:
            src = l["source"].split("(")[-1].rstrip(")")
            with open(os.path.join(ROOT, src), encoding="utf-8") as fh:
                row, _unread = merge_stock.read_list(fh.read(), l["supplier"],
                                                     l["seen"])
            self.assertEqual(row["species"], l["species"], src)

    def test_a_list_from_another_supplier_is_refused(self):
        doc = {"lists": [_list("Big Box Co", ["Achillea borealis"])]}
        self.assertTrue(ls.validate(doc, self.region.nurseries))

    def test_a_ruling_carries_no_reason(self):
        doc = {"rulings": {"Achillea borealis": {"tier": "available",
                                                 "reason": "x"}}}
        self.assertTrue(ls.validate(doc))


class TheAppReadsIt(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Another module in the same run may have pointed the DB elsewhere.
        _plants_mod._DATA_DIR = _TMP_DIR
        _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
        _plants_mod.init_db()

    def tearDown(self):
        ls.set_document(None)

    def test_the_filter_and_easy_to_find(self):
        from src.db.plants import search_plants
        names = {p["scientific_name"]
                 for p in search_plants(stock_in=["available"])}
        self.assertIn("Monarda fistulosa", names)
        self.assertNotIn("Carex aquatilis", names)
        easy = {p["scientific_name"] for p in search_plants(common_only=True)}
        self.assertIn("Campanula rotundifolia", easy)

    def test_the_filter_facet_reads_the_tiers(self):
        from src import plant_filters as pf
        f = next(f for f in pf.FACETS if f.key == "availability")
        self.assertEqual(f.param, "stock_in")
        self.assertEqual(set(f.values), set(ls.TIERS))

    def test_the_plant_page_sentence(self):
        self.assertEqual(ls.clause("Monarda fistulosa"),
                         "Available: Arnica Wildflowers (on its June and "
                         "August 2026 lists).")
        self.assertIn("grown to order", ls.clause("Carex aquatilis"))
        self.assertEqual(ls.clause("Not a plant"), "")

    def test_the_order_file_names_the_listing_supplier(self):
        from src import order_file
        key = __import__("src.region", fromlist=["x"]).default().key
        ls.set_document(key, {"lists": [_list("Arnica Wildflowers",
                                              ["Monarda fistulosa"])]})
        listed = order_file._listed_by(53.52, -113.52)
        self.assertEqual(listed("Monarda fistulosa"),
                         "Arnica Wildflowers (2026-05)")
        ls.set_document(None)
        self.assertEqual(order_file._listed_by(50.45, -104.6)(
            "Monarda fistulosa"), "", "outside the pack, no local supplier")


class ReadingANurseryList(unittest.TestCase):
    """``src/stock_lists`` and ``scripts/merge_stock.py``."""

    def test_a_binomial_wins_over_the_common_name_on_its_line(self):
        """Arnica's "Artemisia ludoviciana - Prairie Sagewort": the catalogue's
        Prairie Sagewort is A. frigida."""
        found, _ = self.match("Artemisia ludoviciana - Prairie Sagewort\n"
                              "# a note line\n"
                              "Helianthus subrhomboideus - Rhombic-leaved "
                              "Sunflower\n", self.table)
        self.assertEqual(found, ["Artemisia ludoviciana",
                                 "Helianthus pauciflorus"])

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
                              "Monarda fistulosa": {"tier": "available",
                                                    "on": "2026-10-16"}}}
        new, _report = merge_stock.merge(doc, review)
        self.assertEqual(len(new["lists"]), 1, "same supplier and date: replaced")
        self.assertEqual(new["lists"][0]["species"],
                         ["Campanula rotundifolia", "Agastache foeniculum"])
        self.assertNotIn("Achillea borealis", new["rulings"])
        self.assertEqual(new["rulings"]["Monarda fistulosa"]["tier"],
                         "available")


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
