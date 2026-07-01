"""
tests/test_ecological_role.py — the "why it matters" plant-role badges (F1).

Covers src/ecological_role.py:
  1. Tag-driven badges (keystone / larval host / bird food / pollinator / N-fixer)
     from the permaculture_uses blob.
  2. Relationship-driven badges from an injected fauna_for_plant() result:
     "Hosts N caterpillars" (distinct larval-host lepidoptera), "Specialist host",
     plus bird / pollinator inferred from relationships.
  3. Priority order and the larval-host count vs. tag fallback.
  4. Empty / no-role plant → [].
  5. Integration: the real seeded DB lazy-fetch path produces sane badges.

Pure (injected fauna_rows keep the logic tests DB-free); one integration test
uses the temp-DB seed.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir so the integration test never touches the real DB.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_role_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.ecological_role import ecological_role_summary  # noqa: E402


def _fauna(common_name, taxon, relationship, specificity="generalist"):
    return {"common_name": common_name, "taxon": taxon,
            "relationship": relationship, "specificity": specificity}


class TestTagBadges(unittest.TestCase):
    def test_keystone_tag(self):
        plant = {"id": 1, "permaculture_uses": "keystone_species,bird_food"}
        badges = ecological_role_summary(plant, fauna_rows=[])
        self.assertIn("Keystone", badges)
        self.assertIn("Bird food", badges)

    def test_host_tag_without_fauna_falls_back(self):
        plant = {"id": 1, "permaculture_uses": "host_plant"}
        badges = ecological_role_summary(plant, fauna_rows=[])
        self.assertIn("Larval host", badges)
        self.assertNotIn("Hosts 1 caterpillar", badges)

    def test_pollinator_and_nfixer_tags(self):
        plant = {"id": 1, "permaculture_uses": "pollinator,nitrogen_fixer"}
        badges = ecological_role_summary(plant, fauna_rows=[])
        self.assertIn("Pollinator plant", badges)
        self.assertIn("Nitrogen fixer", badges)

    def test_no_role_returns_empty(self):
        plant = {"id": 1, "permaculture_uses": "ornamental,hedge"}
        self.assertEqual(ecological_role_summary(plant, fauna_rows=[]), [])

    def test_missing_uses_blob_is_safe(self):
        self.assertEqual(ecological_role_summary({"id": 1}, fauna_rows=[]), [])


class TestRelationshipBadges(unittest.TestCase):
    def test_counts_distinct_larval_host_lepidoptera(self):
        rows = [
            _fauna("Monarch", "lepidoptera", "larval_host", "specialist"),
            _fauna("Eastern Tiger Swallowtail", "lepidoptera", "larval_host"),
            _fauna("Monarch", "lepidoptera", "larval_host", "specialist"),  # dup name
            _fauna("American Robin", "bird", "fruit_food"),     # not a caterpillar
            _fauna("Common Eastern Bumble Bee", "bee", "nectar"),  # not lepidoptera
        ]
        badges = ecological_role_summary({"id": 1}, fauna_rows=rows)
        self.assertIn("Hosts 2 caterpillars", badges)

    def test_singular_caterpillar(self):
        rows = [_fauna("Mourning Cloak", "lepidoptera", "larval_host")]
        badges = ecological_role_summary({"id": 1}, fauna_rows=rows)
        self.assertIn("Hosts 1 caterpillar", badges)

    def test_specialist_badge(self):
        rows = [_fauna("Monarch", "lepidoptera", "larval_host", "specialist")]
        badges = ecological_role_summary({"id": 1}, fauna_rows=rows)
        self.assertIn("Specialist host", badges)

    def test_bird_and_pollinator_inferred_from_relationships(self):
        rows = [
            _fauna("Cedar Waxwing", "bird", "fruit_food"),
            _fauna("Green Sweat Bee", "bee", "pollen"),
        ]
        badges = ecological_role_summary({"id": 1}, fauna_rows=rows)
        self.assertIn("Bird food", badges)
        self.assertIn("Pollinator plant", badges)

    def test_count_supersedes_host_tag(self):
        plant = {"id": 1, "permaculture_uses": "host_plant"}
        rows = [_fauna("A", "lepidoptera", "larval_host"),
                _fauna("B", "lepidoptera", "larval_host")]
        badges = ecological_role_summary(plant, fauna_rows=rows)
        self.assertIn("Hosts 2 caterpillars", badges)
        self.assertNotIn("Larval host", badges)


class TestPriorityOrder(unittest.TestCase):
    def test_keystone_leads_then_caterpillars(self):
        plant = {"id": 1, "permaculture_uses": "keystone_species,bird_food,pollinator"}
        rows = [_fauna("A", "lepidoptera", "larval_host", "specialist"),
                _fauna("B", "lepidoptera", "larval_host")]
        badges = ecological_role_summary(plant, fauna_rows=rows)
        self.assertEqual(badges[0], "Keystone")
        self.assertEqual(badges[1], "Hosts 2 caterpillars")
        self.assertEqual(badges[2], "Specialist host")
        # bird + pollinator come after the relationship-backed badges
        self.assertEqual(badges[3], "Bird food")
        self.assertEqual(badges[4], "Pollinator plant")


class TestRealDBLazyFetch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_lazy_fetch_produces_badges_for_a_keystone_genus(self):
        # Find a seeded plant tagged keystone_species and confirm the lazy
        # fauna fetch path runs and yields badges including "Keystone".
        from src.db.plants import get_connection, get_plant
        with get_connection() as conn:
            row = conn.execute(
                "SELECT pu.plant_id FROM plant_uses pu "
                "JOIN uses u ON u.id = pu.use_id "
                "WHERE u.key = 'keystone_species' LIMIT 1"
            ).fetchone()
        if not row:
            self.skipTest("no keystone_species plant in seed data")
        plant = get_plant(row[0])
        badges = ecological_role_summary(plant)   # fauna fetched lazily by id
        self.assertIn("Keystone", badges)
        self.assertIsInstance(badges, list)


if __name__ == "__main__":
    unittest.main()
