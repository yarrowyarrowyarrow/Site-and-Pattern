"""
tests/test_sk_flora.py

Verifies the V2.16 Saskatchewan flora/fauna expansion (Phase C):

  * the re-tagged catalogue exposes a substantial Moist Mixed Grassland pool
    (the Regina/Saskatoon belt) and SK-native plants,
  * shared prairie species are tagged native to both AB and SK, while Rocky
    Mountain / foothills endemics stay AB-only,
  * the curated SK grassland species were added, including one (Stiff Goldenrod)
    that is SK-native but not AB-native — exercising the native_province filter,
  * the new species are linked to existing fauna (not ecological orphans),
  * fauna carry native_provinces after seeding.

Runs against a fresh temp DB so it never touches real user data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_skflora_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_connection,
    get_all_plants,
    search_plants,
)


class TestSaskatchewanFlora(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.plants = get_all_plants()
        cls.by_sci = {p["scientific_name"]: p for p in cls.plants}

    def test_moist_mixedgrass_pool_is_substantial(self):
        """The Regina/Saskatoon belt should resolve a real design pool."""
        pool = search_plants(ecoregion="moist_mixedgrass")
        self.assertGreater(len(pool), 100)

    def test_sk_native_filter(self):
        sk = search_plants(native_province="SK")
        ab = search_plants(native_province="AB")
        self.assertGreater(len(sk), 100)
        self.assertGreater(len(ab), len(sk))  # AB catalogue is the superset

    def test_curated_species_present(self):
        for sci in ("Sphaeralcea coccinea", "Comandra umbellata",
                    "Oligoneuron rigidum", "Symphyotrichum falcatum",
                    "Packera cana", "Erigeron caespitosus"):
            self.assertIn(sci, self.by_sci, f"{sci} missing from catalogue")

    def test_sk_only_species_not_ab(self):
        """Stiff Goldenrod is native to SK/MB but not AB — the province model
        must distinguish it (native_to_alberta stayed at 0)."""
        sg = self.by_sci["Oligoneuron rigidum"]
        self.assertIn("SK", sg["native_provinces"])
        self.assertIn("MB", sg["native_provinces"])
        self.assertNotIn("AB", sg["native_provinces"])
        self.assertIn(sg, search_plants(native_province="SK"))
        self.assertNotIn(sg, search_plants(native_province="AB"))

    def test_shared_species_tagged_both_provinces(self):
        gm = self.by_sci["Sphaeralcea coccinea"]
        self.assertIn("AB", gm["native_provinces"])
        self.assertIn("SK", gm["native_provinces"])
        self.assertIn("moist_mixedgrass", gm["ecoregion"])

    def test_mountain_endemics_stay_ab_only(self):
        """A subalpine/fescue-only endemic must NOT be tagged native to SK."""
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT native_provinces FROM plants "
                "WHERE ecoregion IN ('subalpine_montane', 'fescue_foothills')"
            ).fetchall()
        finally:
            conn.close()
        self.assertTrue(rows)
        for (np,) in rows:
            self.assertNotIn("SK", (np or ""))

    def test_new_species_have_fauna_links(self):
        conn = get_connection()
        try:
            for cn in ("Stiff Goldenrod", "Scarlet Globemallow"):
                n = conn.execute(
                    "SELECT COUNT(*) FROM plant_fauna pf "
                    "JOIN plants p ON p.id = pf.plant_id "
                    "WHERE p.common_name = ?", (cn,)
                ).fetchone()[0]
                self.assertGreater(n, 0, f"{cn} has no fauna links")
        finally:
            conn.close()

    def test_fauna_native_provinces_seeded(self):
        conn = get_connection()
        try:
            ab = conn.execute(
                "SELECT COUNT(*) FROM fauna "
                "WHERE (',' || COALESCE(native_provinces,'') || ',') LIKE '%,AB,%'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertGreater(ab, 100)


if __name__ == "__main__":
    unittest.main()
