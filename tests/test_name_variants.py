"""
tests/test_name_variants.py — "Burr Oak" finds Bur Oak (V2.86).

Both searches returned nothing for the spelling a good share of gardeners use,
while the plant sat in the catalogue under the other one.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_name_variants_test_")
import src.db.plants as _plants_mod  # noqa: E402
from src.name_variants import query_forms, searchable  # noqa: E402


class TestTheSpellings(unittest.TestCase):

    def test_a_variant_query_gains_the_catalogue_spelling(self):
        self.assertEqual(query_forms("Burr Oak"), ["burr oak", "bur oak"])

    def test_an_ordinary_query_is_left_alone(self):
        self.assertEqual(query_forms("Aspen"), ["aspen"])
        self.assertEqual(query_forms(""), [""])

    def test_only_whole_words_are_swapped(self):
        self.assertEqual(query_forms("burrowing"), ["burrowing"])

    def test_the_site_index_carries_both_spellings(self):
        text = searchable("Bur Oak")
        self.assertIn("bur oak", text)
        self.assertIn("burr oak", text)
        self.assertEqual(searchable("Trembling Aspen"), "trembling aspen")


class TestTheDesktopSearch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod._DATA_DIR = _TMP_DIR
        _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
        _plants_mod.init_db()

    def test_burr_oak_finds_the_bur_oak(self):
        from src.db.plants import search_plants
        names = [r["common_name"] for r in search_plants("Burr Oak")]
        self.assertIn("Bur Oak", names)

    def test_the_catalogue_spelling_still_works(self):
        from src.db.plants import search_plants
        self.assertIn("Bur Oak",
                      [r["common_name"] for r in search_plants("bur oak")])

    def test_a_variant_query_still_combines_with_other_filters(self):
        """The OR of the spellings is parenthesised: without it, a filter
        after the query would bind to only the last spelling."""
        from src.db.plants import search_plants
        self.assertEqual(search_plants("Burr Oak", plant_type="grass"), [])


if __name__ == "__main__":
    unittest.main()
