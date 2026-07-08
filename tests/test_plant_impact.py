"""
tests/test_plant_impact.py — the "pull-a-plant" impact simulator (F46).

Covers src/plant_impact.py against the seeded temp DB:
  1. Pulling a keystone host drops supported species and lowers the score;
     the losses are named per taxon.
  2. Redundancy honesty (P9): with a second copy placed, pulling one loses
     nothing and the verdict says so.
  3. A plant that isn't placed → None.
  4. The result dict is JSON-shaped with the documented keys.
  5. The scripting-API wrapper (permadesign_api.pull_plant_impact) is exported.
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_impact_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection  # noqa: E402
from src.plant_impact import pull_plant_impact  # noqa: E402


def _pid(name):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id FROM plants WHERE common_name = ?", (name,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _first_host_with_fauna():
    """A plant id that supports several fauna, for a meaningful pull."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT pf.plant_id, COUNT(DISTINCT pf.fauna_id) n
               FROM plant_fauna pf GROUP BY pf.plant_id
               ORDER BY n DESC LIMIT 1""").fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class TestPullPlantImpact(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.keystone = _first_host_with_fauna()
        assert cls.keystone is not None
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM plants WHERE id != ? LIMIT 1",
                (cls.keystone,)).fetchone()
            cls.filler = row[0]
        finally:
            conn.close()
        assert cls.filler != cls.keystone

    def _design(self):
        # keystone host + a distinct filler so removing the keystone is meaningful
        return [{"plant_id": self.keystone, "common_name": "Keystone host"},
                {"plant_id": self.filler, "common_name": "Filler plant"}]

    def test_pull_keystone_loses_species(self):
        r = pull_plant_impact(self._design(), [], self.keystone)
        self.assertIsNotNone(r)
        self.assertEqual(r["remaining_copies"], 0)
        self.assertGreater(r["species_supported"], 0)
        self.assertGreater(r["species_lost"], 0, "a keystone should lose species")
        self.assertLessEqual(r["score_after"], r["score_before"])
        # losses are named per taxon
        named = sum(len(v) for v in r["species_lost_by_taxon"].values())
        self.assertEqual(named, r["species_lost"])
        self.assertIn(str(r["species_lost"]), r["verdict"])

    def test_redundancy_loses_nothing(self):
        design = self._design() + [{"plant_id": self.keystone,
                                    "common_name": "Keystone host"}]
        r = pull_plant_impact(design, [], self.keystone)
        self.assertEqual(r["remaining_copies"], 1)
        self.assertEqual(r["species_lost"], 0)
        self.assertEqual(r["species_lost_by_taxon"], {})
        self.assertIn("resilience", r["verdict"].lower())

    def test_not_placed_returns_none(self):
        self.assertIsNone(pull_plant_impact(self._design(), [], 10_000_000))

    def test_result_is_json_shaped(self):
        r = pull_plant_impact(self._design(), [], self.keystone)
        json.dumps(r)      # must be serialisable
        for key in ("plant_id", "common_name", "score_before", "score_after",
                    "score_delta", "species_supported", "species_lost",
                    "species_lost_by_taxon", "food_web_before", "food_web_after",
                    "chain_snaps", "verdict"):
            self.assertIn(key, r)

    def test_api_surface_exported(self):
        import src.permadesign_api as api
        self.assertIn("pull_plant_impact", api.__all__)
        self.assertTrue(callable(api.pull_plant_impact))


if __name__ == "__main__":
    unittest.main()
