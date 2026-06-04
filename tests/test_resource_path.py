"""
tests/test_resource_path.py

Guards the bundled-resource path resolution that lets the app find
``schema.sql`` and the seed JSON inside a PyInstaller build. This is the
fix for the historic installed-build crash:

    Could not initialise the plant database:
        [Errno 2] No such file or directory: '...\\schema.sql'
    sqlite3.OperationalError: no such table: polycultures

Covers three things:
  1. In a normal source checkout, ``resource_path`` points at files that
     actually exist (schema, seed JSON, map HTML).
  2. In a simulated frozen build (``sys.frozen`` + ``sys._MEIPASS``),
     ``resource_path`` resolves under ``_MEIPASS`` instead of the repo.
  3. End-to-end: ``init_db()`` (which opens ``schema.sql`` via
     ``resource_path``) creates the ``polycultures`` table and seeds the
     full plant catalogue.

Each DB-touching test runs against a fresh temp DB so we never touch real
user data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_respath_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.resources import resource_path  # noqa: E402


class TestResourcePathDevMode(unittest.TestCase):
    """In a source checkout every bundled resource must resolve to a real file."""

    def test_schema_resolves_to_existing_file(self):
        path = resource_path("src", "db", "schema.sql")
        self.assertTrue(os.path.isfile(path), f"schema.sql not found at {path}")

    def test_seed_json_resolve_to_existing_files(self):
        for name in ("plants_master.json", "garden_plants.json",
                     "fauna_master.json", "plant_fauna_master.json"):
            path = resource_path("data", name)
            self.assertTrue(os.path.isfile(path), f"{name} not found at {path}")

    def test_map_html_resolves_to_existing_file(self):
        path = resource_path("html", "map.html")
        self.assertTrue(os.path.isfile(path), f"map.html not found at {path}")

    def test_plants_module_constants_point_at_real_files(self):
        # The constants are computed at import time via resource_path — make
        # sure that wiring actually lands on the shipped files.
        self.assertTrue(os.path.isfile(_plants_mod._SCHEMA_PATH))
        self.assertTrue(os.path.isfile(_plants_mod._MASTER_JSON_PATH))


class TestResourcePathFrozen(unittest.TestCase):
    """Simulate a PyInstaller build: resource_path must use sys._MEIPASS."""

    def setUp(self):
        self._orig_frozen = getattr(sys, "frozen", None)
        self._orig_meipass = getattr(sys, "_MEIPASS", None)
        self._meipass = tempfile.mkdtemp(prefix="permadesign_meipass_")
        # Mirror the spec's datas layout inside the fake bundle root.
        os.makedirs(os.path.join(self._meipass, "src", "db"))
        os.makedirs(os.path.join(self._meipass, "data"))
        open(os.path.join(self._meipass, "src", "db", "schema.sql"), "w").close()

    def tearDown(self):
        if self._orig_frozen is None:
            if hasattr(sys, "frozen"):
                del sys.frozen
        else:
            sys.frozen = self._orig_frozen
        if self._orig_meipass is None:
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS
        else:
            sys._MEIPASS = self._orig_meipass

    def test_resolves_under_meipass_when_frozen(self):
        sys.frozen = True
        sys._MEIPASS = self._meipass
        self.assertEqual(
            resource_path("src", "db", "schema.sql"),
            os.path.join(self._meipass, "src", "db", "schema.sql"),
        )
        self.assertEqual(
            resource_path("data", "plants_master.json"),
            os.path.join(self._meipass, "data", "plants_master.json"),
        )


class TestInitDbFindsSchema(unittest.TestCase):
    """End-to-end guard for the exact installed-build failure."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_polycultures_table_exists(self):
        conn = get_connection()
        try:
            tables = {
                r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        # The historic crash was "no such table: polycultures".
        self.assertIn("polycultures", tables)

    def test_plant_catalogue_seeded(self):
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM plants").fetchone()[0]
        finally:
            conn.close()
        # Full native catalogue is 400+; a found-and-applied schema + seed
        # JSON is the only way this is non-trivially populated.
        self.assertGreater(n, 100)


if __name__ == "__main__":
    unittest.main()
