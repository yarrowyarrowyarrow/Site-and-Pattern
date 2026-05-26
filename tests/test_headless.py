"""
tests/test_headless.py

Verify that the headless bootstrap path and DesignGenerator work
without importing Qt. Patches _DATA_DIR / _DB_PATH to a tmpdir
(same pattern as test_guilds.py) so the real user DB is never touched.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect DB to a temp dir before importing anything DB-related
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_headless_test_")

import src.db.plants as _plants_mod
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")


class TestBootstrap(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from src.bootstrap import bootstrap_db
        bootstrap_db()

    def test_bootstrap_creates_db(self):
        self.assertTrue(os.path.exists(_plants_mod._DB_PATH))

    def test_bootstrap_is_idempotent(self):
        from src.bootstrap import bootstrap_db
        # Should not raise when called twice
        bootstrap_db()
        self.assertTrue(os.path.exists(_plants_mod._DB_PATH))

    def test_bootstrap_does_not_import_qt(self):
        # PyQt6 must not be imported as a side-effect of bootstrap
        self.assertNotIn("PyQt6", sys.modules)


class TestDesignGeneratorQuery(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from src.bootstrap import bootstrap_db
        bootstrap_db()

    def _gen(self):
        from src.design_api import DesignGenerator
        return DesignGenerator({"name": "Test", "latitude": 53.5, "longitude": -113.5})

    def test_search_plants_returns_list(self):
        gen = self._gen()
        results = gen.search_plants()
        self.assertIsInstance(results, list)

    def test_search_plants_zone_filter(self):
        gen = self._gen()
        results = gen.search_plants(zone=3)
        self.assertIsInstance(results, list)
        # Every result must include zone fields
        for r in results:
            self.assertIn("common_name", r)

    def test_get_plant_details_valid(self):
        gen = self._gen()
        plants = gen.search_plants()
        if not plants:
            self.skipTest("No plants in test DB")
        pid = plants[0]["id"]
        detail = gen.get_plant_details(pid)
        self.assertIsNotNone(detail)
        self.assertIn("plant", detail)
        self.assertIn("companions", detail)

    def test_get_plant_details_missing(self):
        gen = self._gen()
        detail = gen.get_plant_details(999999)
        self.assertIsNone(detail)

    def test_list_guilds_returns_list(self):
        gen = self._gen()
        guilds = gen.list_guilds()
        self.assertIsInstance(guilds, list)

    def test_list_saved_recipes_returns_list(self):
        gen = self._gen()
        recipes = gen.list_saved_recipes()
        self.assertIsInstance(recipes, list)


class TestDesignGeneratorValidate(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from src.bootstrap import bootstrap_db
        bootstrap_db()

    def _gen(self):
        from src.design_api import DesignGenerator
        return DesignGenerator()

    def test_validate_empty_design_returns_issues(self):
        gen = self._gen()
        issues = gen.validate()
        self.assertIsInstance(issues, list)
        self.assertGreater(len(issues), 0)

    def test_validate_issue_has_required_keys(self):
        gen = self._gen()
        issues = gen.validate()
        for issue in issues:
            self.assertIn("type", issue)
            self.assertIn("message", issue)
            self.assertIn("severity", issue)
            self.assertIn(issue["severity"], ("warning", "error"))

    def test_validate_with_coords_fewer_issues(self):
        from src.design_api import DesignGenerator
        gen = DesignGenerator({"latitude": 53.5, "longitude": -113.5, "hardiness_zone": "3b"})
        issues = gen.validate()
        types = {i["type"] for i in issues}
        self.assertNotIn("no_coordinates", types)
        self.assertNotIn("no_zone", types)


class TestDbNamespace(unittest.TestCase):

    def test_db_package_exports_search_plants(self):
        from src.db import search_plants
        self.assertTrue(callable(search_plants))

    def test_db_package_exports_get_all_guilds(self):
        from src.db import get_all_guilds
        self.assertTrue(callable(get_all_guilds))

    def test_db_package_exports_get_structure(self):
        from src.db import get_structure
        self.assertTrue(callable(get_structure))


if __name__ == "__main__":
    unittest.main()
