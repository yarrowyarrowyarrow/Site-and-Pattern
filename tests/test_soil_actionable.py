"""
tests/test_soil_actionable.py — soil pH actually constrains plant matching
(V1.67). Headless DB test against a temp DB (mirrors test_polycultures).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_soilph_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import get_connection, init_db, search_plants  # noqa: E402


class TestSoilPhFilter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        conn = get_connection()
        try:
            # Tolerant of alkaline soil (pH 6–8) vs acid-only (pH 4–6).
            conn.execute(
                "INSERT INTO plants (common_name, plant_type, soil_ph_min, "
                "soil_ph_max) VALUES (?,?,?,?)",
                ("ZZSoilTest Tolerant", "herb", 6.0, 8.0))
            conn.execute(
                "INSERT INTO plants (common_name, plant_type, soil_ph_min, "
                "soil_ph_max) VALUES (?,?,?,?)",
                ("ZZSoilTest Acidic", "herb", 4.0, 6.0))
            conn.commit()
        finally:
            conn.close()

    def _names(self, **kw):
        return {p["common_name"] for p in
                search_plants(query="ZZSoilTest", **kw)}

    def test_no_soil_filter_returns_both(self):
        names = self._names()
        self.assertEqual(len([n for n in names if n.startswith("ZZSoilTest")]),
                         2)

    def test_alkaline_ph_excludes_acid_only_plant(self):
        names = self._names(soil_ph=7.5)
        self.assertIn("ZZSoilTest Tolerant", names)
        self.assertNotIn("ZZSoilTest Acidic", names)

    def test_acid_ph_keeps_acid_excludes_alkaline(self):
        # pH 5.0 is within Acidic [4,6]; Tolerant [6,8] excludes it.
        names = self._names(soil_ph=5.0)
        self.assertIn("ZZSoilTest Acidic", names)
        self.assertNotIn("ZZSoilTest Tolerant", names)


if __name__ == "__main__":
    unittest.main()
