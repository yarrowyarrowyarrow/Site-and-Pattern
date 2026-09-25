"""
tests/test_pending_species.py — trees waiting for a flora, and the keystone
genera (V2.86).

Seven native trees were written in a session that could not reach VASCAN.
Since V2.80 a species ships only with its nativity read from a flora, so they
wait in `data/plants_pending_flora.json` until the archive run promotes them.
These pin that the wait is real (nothing seeds from the file) and that the
rows are held to the catalogue's rules while they wait.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_pending_test_")
import src.db.plants as _plants_mod  # noqa: E402
from src import data_quality as dq  # noqa: E402
from src import pending_species  # noqa: E402

TREES = {"Salix amygdaloides", "Populus deltoides", "Populus angustifolia",
         "Acer negundo", "Crataegus chrysocarpa", "Juniperus scopulorum",
         "Ulmus americana"}


class TestTheShippedPendingRows(unittest.TestCase):

    def test_the_seven_trees_are_waiting(self):
        self.assertEqual(set(pending_species.names()), TREES)

    def test_they_pass_the_catalogues_own_rules(self):
        errors, _ = dq.validate_pending_species()
        self.assertEqual(errors, [])

    def test_none_claims_a_source_it_has_not_got(self):
        for row in pending_species.load():
            self.assertFalse(row.get("native_provinces_source"),
                             row["scientific_name"])

    def test_the_gate_reads_them(self):
        """A validator nobody calls is a comment."""
        with mock.patch.object(dq, "validate_pending_species",
                               return_value=(["sentinel"], [])):
            errors, _ = dq.validate_all()
        self.assertIn("sentinel", errors)


class TestNothingSeedsFromThePendingFile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod._DATA_DIR = _TMP_DIR
        _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
        _plants_mod.init_db()

    def test_no_pending_tree_is_in_the_database(self):
        from src.db.plants import get_connection
        with get_connection() as conn:
            got = {r[0] for r in conn.execute(
                "SELECT scientific_name FROM plants")}
        self.assertEqual(got & TREES, set())


class TestWhatAPendingRowMayNotBe(unittest.TestCase):

    def _errors(self, rows):
        with mock.patch.object(pending_species, "load", return_value=rows):
            return dq.validate_pending_species()[0]

    def _row(self, **kw):
        row = {"common_name": "Testing Tree", "scientific_name": "Testus arbor",
               "plant_type": "tree", "native_provinces": "AB"}
        row.update(kw)
        return row

    def test_a_clean_row_passes(self):
        self.assertEqual(self._errors([self._row()]), [])

    def test_it_may_not_carry_a_source(self):
        errs = self._errors([self._row(native_provinces_source="flora")])
        self.assertTrue(any("nativity source" in e for e in errs))

    def test_it_may_not_already_be_in_the_catalogue(self):
        errs = self._errors([self._row(scientific_name="Populus tremuloides",
                                       common_name="Some Aspen")])
        self.assertTrue(any("already in the catalogue" in e for e in errs))

    def test_it_may_not_reverse_an_exclusion(self):
        errs = self._errors([self._row(scientific_name="Rudbeckia hirta",
                                       common_name="Some Susan")])
        self.assertTrue(any("excluded_taxa" in e for e in errs))

    def test_it_may_not_wear_another_rows_name(self):
        errs = self._errors([self._row(common_name="Bur Oak (Burr Oak)")])
        self.assertTrue(any("common name" in e for e in errs))


class TestTheKeystoneGenera(unittest.TestCase):

    def _errors(self, pending):
        with mock.patch.object(pending_species, "load", return_value=pending):
            return dq.validate_keystone_genera()[0]

    def test_the_shipped_catalogue_follows_the_rule(self):
        self.assertEqual(dq.validate_keystone_genera()[0], [])

    def test_birch_and_oak_are_keystone_now(self):
        """Two of Tallamy & Shropshire's top five woody genera were the only
        ones missing, so Paper Birch scored no keystone credit and every
        willow did."""
        self.assertIn("Betula", dq.KEYSTONE_GENERA)
        self.assertIn("Quercus", dq.KEYSTONE_GENERA)

    def test_a_member_without_the_tag_fails(self):
        errs = self._errors([{"scientific_name": "Salix testa",
                              "common_name": "Test Willow",
                              "permaculture_uses": "host_plant"}])
        self.assertTrue(any("Salix testa" in e for e in errs))

    def test_a_tag_outside_the_genera_fails(self):
        errs = self._errors([{"scientific_name": "Viola testa",
                              "common_name": "Test Violet",
                              "permaculture_uses": "keystone_species"}])
        self.assertTrue(any("Viola testa" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
