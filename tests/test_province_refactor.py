"""
tests/test_province_refactor.py

Verifies the V2.15 province-neutral data-model refactor (schema v42):

  * the ``plants.ab_ecoregion`` column is renamed to ``plants.ecoregion``
    (fresh install has no stray ``ab_ecoregion`` column),
  * a ``native_provinces`` column is added to ``plants`` and ``fauna`` and
    seeded (derived from ``native_to_alberta`` for the AB seed data),
  * ``search_plants`` accepts both the legacy ``ab_ecoregion`` filter and the
    new ``ecoregion`` filter, plus a ``native_province`` filter,
  * read-side plant dicts still expose ``ab_ecoregion`` as a back-compat alias
    of ``ecoregion`` (so the frozen API / downstream consumers keep working),
  * an existing v41 DB migrates cleanly to v42.

Each test runs against a fresh temp DB so we never touch the real user data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_province_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_connection,
    get_all_plants,
    search_plants,
    _SCHEMA_VERSION,
)


def _plant_columns(conn) -> set:
    return {r[1] for r in conn.execute("PRAGMA table_info(plants)").fetchall()}


class TestProvinceRefactor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_schema_version_is_at_least_42(self):
        self.assertGreaterEqual(_SCHEMA_VERSION, 42)

    def test_ecoregion_column_renamed_no_stray(self):
        conn = get_connection()
        try:
            cols = _plant_columns(conn)
        finally:
            conn.close()
        self.assertIn("ecoregion", cols)
        self.assertNotIn("ab_ecoregion", cols,
                         "fresh install must not carry a stray ab_ecoregion column")

    def test_native_provinces_columns_exist(self):
        conn = get_connection()
        try:
            pcols = _plant_columns(conn)
            fcols = {r[1] for r in conn.execute(
                "PRAGMA table_info(fauna)").fetchall()}
        finally:
            conn.close()
        self.assertIn("native_provinces", pcols)
        self.assertIn("native_provinces", fcols)

    def test_native_provinces_seeded_from_native_to_alberta(self):
        """Every AB-native seed plant gets native_provinces containing 'AB'."""
        conn = get_connection()
        try:
            ab_natives = conn.execute(
                "SELECT COUNT(*) FROM plants WHERE native_to_alberta = 1"
            ).fetchone()[0]
            tagged_ab = conn.execute(
                "SELECT COUNT(*) FROM plants "
                "WHERE (',' || COALESCE(native_provinces,'') || ',') LIKE '%,AB,%'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(ab_natives, 0)
        self.assertGreaterEqual(tagged_ab, ab_natives)

    def test_read_side_ab_ecoregion_alias(self):
        """Plant dicts expose ab_ecoregion == ecoregion for back-compat."""
        plants = get_all_plants()
        sample = next((p for p in plants if p.get("ecoregion")), None)
        self.assertIsNotNone(sample, "expected at least one ecoregion-tagged plant")
        self.assertEqual(sample["ab_ecoregion"], sample["ecoregion"])

    def test_search_ecoregion_and_legacy_param_agree(self):
        new = search_plants(ecoregion="mixedgrass_prairie")
        legacy = search_plants(ab_ecoregion="mixedgrass_prairie")
        self.assertTrue(new, "expected mixedgrass plants in the seed data")
        self.assertEqual(len(new), len(legacy))

    def test_search_native_province_filter(self):
        ab = search_plants(native_province="AB")
        self.assertTrue(ab, "expected AB-native plants")
        # A province with no seeded natives yet (pre Phase C) returns nothing,
        # never raises.
        self.assertEqual(search_plants(native_province="QC"), [])


class TestV41Upgrade(unittest.TestCase):
    """An existing v41 DB (ab_ecoregion column, no native_provinces) migrates
    to v42 on the next init_db."""

    def test_upgrade_renames_and_adds_columns(self):
        import sqlite3
        tmp = tempfile.mkdtemp(prefix="permadesign_v41_upgrade_")
        orig_dir, orig_path = _plants_mod._DATA_DIR, _plants_mod._DB_PATH
        _plants_mod._DATA_DIR = tmp
        _plants_mod._DB_PATH = os.path.join(tmp, "permadesign_test.db")
        try:
            init_db()  # builds a current (v42) DB
            # Downgrade the shape to look like v41.
            conn = sqlite3.connect(_plants_mod._DB_PATH)
            conn.execute("ALTER TABLE plants RENAME COLUMN ecoregion TO ab_ecoregion")
            conn.execute("ALTER TABLE plants DROP COLUMN native_provinces")
            conn.execute("DELETE FROM _schema_version")
            conn.execute("INSERT INTO _schema_version VALUES (41)")
            conn.commit()
            conn.close()

            init_db()  # should migrate v41 -> v42

            conn = sqlite3.connect(_plants_mod._DB_PATH)
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(plants)").fetchall()}
            ver = conn.execute(
                "SELECT version FROM _schema_version").fetchone()[0]
            conn.close()
            self.assertEqual(ver, _SCHEMA_VERSION)
            self.assertIn("ecoregion", cols)
            self.assertNotIn("ab_ecoregion", cols)
            self.assertIn("native_provinces", cols)
        finally:
            _plants_mod._DATA_DIR, _plants_mod._DB_PATH = orig_dir, orig_path


if __name__ == "__main__":
    unittest.main()
