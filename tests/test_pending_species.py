"""
tests/test_pending_species.py — trees waiting for a flora, and the keystone
genera (V2.86; the trees promoted in V2.87).

Seven native trees were written in a session that could not reach VASCAN.
Since V2.80 a species ships only with its nativity read from a flora, so they
waited in `data/plants_pending_flora.json` until the author's archive run
promoted them (V2.87). These pin that the wait is real (nothing seeds from the
file), that a pending row is held to the catalogue's rules, and that what
arrived carries VASCAN's answer rather than the one written on the row.
"""

import json
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

#: VASCAN's provinces for the seven, as the V2.87 run wrote them. Two differ
#: from what the pending rows said (Juniper and Narrowleaf Cottonwood were
#: written AB), which is the point of writing the checklist's answer.
TREES = {"Salix amygdaloides": "AB,SK", "Populus deltoides": "AB,SK",
         "Populus angustifolia": "AB,SK", "Acer negundo": "AB,SK",
         "Crataegus chrysocarpa": "AB,SK", "Juniperus scopulorum": "AB,SK",
         "Ulmus americana": "SK"}


def _catalogue() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "data",
                        "plants_master.json")
    with open(path, encoding="utf-8") as fh:
        return {r["scientific_name"]: r for r in json.load(fh)}


class TestTheTreesArrived(unittest.TestCase):

    def test_the_pending_file_is_empty_again(self):
        self.assertEqual(pending_species.names(), [])

    def test_each_tree_carries_vascans_answer(self):
        rows = _catalogue()
        for sci, provinces in TREES.items():
            self.assertIn(sci, rows)
            self.assertEqual(rows[sci]["native_provinces"], provinces, sci)
            self.assertEqual(rows[sci]["native_provinces_source"], "flora",
                             sci)
            self.assertEqual(rows[sci]["native_to_alberta"],
                             1 if "AB" in provinces else 0, sci)

    def test_each_tree_has_occurrence_data(self):
        """The GBIF run the hand-over asked for: without it a tree has no range
        map and ranks as unrecorded near every yard."""
        from src.ecoregion_ranges import parse_document as regions
        from src.species_range import parse_document as ranges
        here = os.path.join(os.path.dirname(__file__), "..", "data")
        with open(os.path.join(here, "plant_ranges.json"),
                  encoding="utf-8") as fh:
            grid = ranges(json.load(fh))
        with open(os.path.join(here, "plant_ecoregions.json"),
                  encoding="utf-8") as fh:
            eco = regions(json.load(fh))
        for sci in TREES:
            self.assertTrue(grid.get(sci), sci)
            self.assertTrue(eco.get(sci), sci)


class TestThePendingRowsTheGateReads(unittest.TestCase):

    def test_they_pass_the_catalogues_own_rules(self):
        errors, _ = dq.validate_pending_species()
        self.assertEqual(errors, [])

    def test_the_gate_reads_them(self):
        """A validator nobody calls is a comment."""
        with mock.patch.object(dq, "validate_pending_species",
                               return_value=(["sentinel"], [])):
            errors, _ = dq.validate_all()
        self.assertIn("sentinel", errors)


class TestNothingSeedsFromThePendingFile(unittest.TestCase):

    def test_a_pending_row_never_reaches_the_database(self):
        tmp = tempfile.mkdtemp(prefix="pending_seed_")
        pending = os.path.join(tmp, "plants_pending_flora.json")
        with open(pending, "w", encoding="utf-8") as fh:
            json.dump([{"common_name": "Testing Tree",
                        "scientific_name": "Testus arbor",
                        "plant_type": "tree", "native_provinces": "AB"}], fh)
        with mock.patch.object(pending_species, "path",
                               return_value=__import__("pathlib").Path(
                                   pending)):
            self.assertEqual(pending_species.names(), ["Testus arbor"])
            _plants_mod._DATA_DIR = _TMP_DIR
            _plants_mod._DB_PATH = os.path.join(_TMP_DIR,
                                                "permadesign_test.db")
            _plants_mod.init_db()
            from src.db.plants import get_connection
            with get_connection() as conn:
                got = {r[0] for r in conn.execute(
                    "SELECT scientific_name FROM plants")}
        self.assertNotIn("Testus arbor", got)
        self.assertIn("Ulmus americana", got)


class TestTheRebuildSkipsExcludedSpecies(unittest.TestCase):
    """V2.87. The point cache keeps every record ever harvested, and a full
    rebuild of the range grid republished six excluded species."""

    def test_no_derived_file_carries_an_excluded_species(self):
        errors, _ = dq.validate_excluded_taxa()
        self.assertEqual(errors, [])

    def test_the_range_seeder_skips_them(self):
        import scripts.seed_species_ranges as S
        seen = {}

        def fake_derive(cache, **_kw):
            seen.update(cache)
            return {}, {}
        cache = {"Helianthus annuus": [(50.0, -110.0)],
                 "Testus arbor": [(50.0, -110.0)]}
        with mock.patch("scripts.seed_ecoregion_ranges.read_cache",
                        return_value=cache), \
                mock.patch.object(S, "derive", side_effect=fake_derive), \
                mock.patch("builtins.print"):
            S.main(["--dry-run", "--quiet"])
        self.assertIn("Testus arbor", seen)
        self.assertNotIn("Helianthus annuus", seen)


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
