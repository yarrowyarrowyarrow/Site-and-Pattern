"""
tests/test_recipes_table_kept.py — an old database with recipes still opens
(V3.22, RM-6).

``src/db/recipes.py`` was deleted: nothing had read its table since the
plant-mix builder stopped using recipes. The table stays (dropping it would
throw away rows a user made), so a database holding recipe rows must open,
reseed and keep them.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_recipes_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import get_connection, init_db  # noqa: E402


class AnOldDatabaseWithRecipesOpens(unittest.TestCase):

    def test_recipe_rows_survive_a_reopen_and_a_reseed(self):
        init_db()
        conn = get_connection()
        try:
            conn.execute("INSERT INTO polyculture_recipes (name) "
                         "VALUES ('Old prairie mix')")
            conn.commit()
            # One version back, so the next init reseeds as an upgrade would.
            _plants_mod._set_schema_version(conn,
                                            _plants_mod._SCHEMA_VERSION - 1)
        finally:
            conn.close()
        init_db()
        conn = get_connection()
        try:
            names = [r[0] for r in conn.execute(
                "SELECT name FROM polyculture_recipes")]
        finally:
            conn.close()
        self.assertEqual(names, ["Old prairie mix"])

    def test_the_module_is_gone(self):
        import importlib.util
        self.assertIsNone(importlib.util.find_spec("src.db.recipes"))


if __name__ == "__main__":
    unittest.main()
