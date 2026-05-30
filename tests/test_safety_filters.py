"""
tests/test_safety_filters.py

Tests the schema-v18 safety / spread filters added to ``search_plants`` in
V1.44 chunk 2: ``pet_safe_only``, ``kid_safe_only`` and ``well_behaved_only``.

These are DENYLIST filters — they exclude only plants we have classified as
toxic / thorny / aggressive; unassessed plants still pass. The tests assert
both halves of that contract (known-bad excluded, benign-unassessed kept).

Headless; redirects the DB to a tempdir so the real user DB is untouched.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.db.plants as _plants_mod  # noqa: E402

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_safety_test_")
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, search_plants  # noqa: E402


def _names(rows):
    return {r["common_name"] for r in rows}


class TestSafetyFilters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.all_names = _names(search_plants())

    # ── Seed sanity: the new columns actually populated from JSON ────────────
    def test_seed_populated_toxicity(self):
        baneberry = search_plants(query="Red Baneberry")
        self.assertTrue(baneberry, "Red Baneberry should be in the catalogue")
        self.assertEqual(baneberry[0]["toxicity_pets"], "high")
        self.assertEqual(baneberry[0]["toxicity_humans"], "high")

    def test_seed_populated_death_camas_is_high(self):
        # Safety-critical: death camas must be flagged toxic.
        for row in search_plants(query="Camas"):
            if "camas" in row["common_name"].lower():
                self.assertEqual(row["toxicity_humans"], "high",
                                 f"{row['common_name']} should be high-toxic")

    # ── pet_safe_only ───────────────────────────────────────────────────────
    def test_pet_safe_excludes_known_toxic(self):
        safe = _names(search_plants(pet_safe_only=True))
        for toxic in ("Red Baneberry", "Showy Milkweed", "Chokecherry",
                      "Yarrow", "Nodding Onion"):
            if toxic in self.all_names:
                self.assertNotIn(toxic, safe, f"{toxic} must be excluded")

    def test_pet_safe_is_denylist_not_allowlist(self):
        # Most of the catalogue is unassessed and therefore still returned.
        safe = search_plants(pet_safe_only=True)
        self.assertGreater(len(safe), 0.7 * len(self.all_names))
        # A benign, unassessed plant is kept.
        self.assertIn("Saskatoon Berry", _names(safe))

    # ── kid_safe_only (toxic-to-humans OR thorny) ───────────────────────────
    def test_kid_safe_excludes_toxic_and_thorny(self):
        kid = _names(search_plants(kid_safe_only=True))
        for excluded in ("Red Baneberry",        # toxic to humans
                         "Prickly Wild Rose",     # thorns
                         "Black Hawthorn"):       # thorns
            if excluded in self.all_names:
                self.assertNotIn(excluded, kid, f"{excluded} must be excluded")

    def test_kid_safe_keeps_pet_toxic_but_human_edible(self):
        # Wild chives are toxic to pets (onion) but edible for people and
        # thornless — so they pass the KID filter though not the PET filter.
        if "Wild Chives" in self.all_names:
            self.assertIn("Wild Chives", _names(search_plants(kid_safe_only=True)))
            self.assertNotIn("Wild Chives", _names(search_plants(pet_safe_only=True)))

    # ── well_behaved_only ───────────────────────────────────────────────────
    def test_well_behaved_excludes_aggressive(self):
        wb = _names(search_plants(well_behaved_only=True))
        for excluded in ("Wild Mint", "Canada Goldenrod", "Common Horsetail"):
            if excluded in self.all_names:
                self.assertNotIn(excluded, wb, f"{excluded} must be excluded")

    def test_well_behaved_keeps_slow_spreaders(self):
        # slow_spreader / clumping / unassessed are well-behaved enough to pass.
        wb = _names(search_plants(well_behaved_only=True))
        if "Red Osier Dogwood" in self.all_names:   # tagged slow_spreader
            self.assertIn("Red Osier Dogwood", wb)

    # ── Composition with each other and existing filters ────────────────────
    def test_filters_compose_without_error(self):
        rows = search_plants(native_only=True, pet_safe_only=True,
                             kid_safe_only=True, well_behaved_only=True)
        self.assertIsInstance(rows, list)
        names = _names(rows)
        self.assertNotIn("Red Baneberry", names)
        self.assertNotIn("Prickly Wild Rose", names)


if __name__ == "__main__":
    unittest.main()
