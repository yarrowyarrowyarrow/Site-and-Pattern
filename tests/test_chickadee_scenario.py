"""
tests/test_chickadee_scenario.py — the feed-a-chickadee scenario (F47).

Covers src/chickadee_scenario.py:
  1. No host plants → status 'none', zero capacity, hungry-brood verdict.
  2. Capacity scales with instance count × keystone rank; low < high.
  3. status thresholds (short / partway / clears) against the 6,000–9,000 need.
  4. host_plants ranked richest-first; JSON-friendly shape.
  5. Honest range: caterpillars reported as a band, never one number.
  6. Scripting-API surface (chickadee_provision) + integration on the temp DB.

Logic tests inject ``get_keystone`` / ``supported_leps`` (DB-free); the last
class uses the seeded temp DB.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_chickadee_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.chickadee_scenario import (  # noqa: E402
    chickadee_provision, BROOD_NEED_LOW, BROOD_NEED_HIGH,
    CATS_PER_HOST_SPECIES_LOW, CATS_PER_HOST_SPECIES_HIGH,
)


def _placed(*pairs):
    """Build a placed-plant list from ``(plant_id, name)`` pairs (one per copy)."""
    return [{"plant_id": pid, "common_name": name} for pid, name in pairs]


# Fake keystone ranks: plant 1 hosts 20 lep species (a heavy keystone),
# plant 2 hosts 3, plant 9 hosts none.
_RANKS = {1: 20, 2: 3, 9: 0}


def _fake_keystone(pid):
    return _RANKS.get(pid, 0)


def _fake_leps(plant_ids):
    # distinct lep species = sum of ranks, capped arbitrarily; only needs to be
    # deterministic and >0 when a host is present.
    return set(range(sum(_RANKS.get(p, 0) for p in set(plant_ids))))


class TestChickadeeLogic(unittest.TestCase):

    def _run(self, placed):
        return chickadee_provision(placed, get_keystone=_fake_keystone,
                                   supported_leps=_fake_leps)

    def test_no_host_plants(self):
        r = self._run(_placed((9, "Barren Sedge")))
        self.assertEqual(r["status"], "none")
        self.assertEqual(r["caterpillars_low"], 0)
        self.assertEqual(r["caterpillars_high"], 0)
        self.assertEqual(r["host_plants"], [])
        self.assertIn("hungry", r["verdict"].lower())

    def test_empty_design(self):
        r = self._run([])
        self.assertEqual(r["status"], "none")
        self.assertEqual(r["caterpillars_high"], 0)

    def test_capacity_scales_with_count_and_rank(self):
        one = self._run(_placed((1, "Willow")))
        self.assertEqual(one["caterpillars_low"],
                         1 * 20 * CATS_PER_HOST_SPECIES_LOW)
        self.assertEqual(one["caterpillars_high"],
                         1 * 20 * CATS_PER_HOST_SPECIES_HIGH)
        # Two copies double the capacity.
        two = self._run(_placed((1, "Willow"), (1, "Willow")))
        self.assertEqual(two["caterpillars_low"], 2 * one["caterpillars_low"])
        # Low is always the conservative end.
        self.assertLess(one["caterpillars_low"], one["caterpillars_high"])

    def test_status_thresholds(self):
        # 1 heavy keystone (20 species): 3,000–8,000 → optimistic clears min,
        # conservative doesn't → 'partway'.
        r1 = self._run(_placed((1, "Willow")))
        self.assertEqual(r1["caterpillars_low"], 3000)
        self.assertEqual(r1["caterpillars_high"], 8000)
        self.assertEqual(r1["status"], "partway")
        # 3 heavy keystones: 9,000–24,000 → conservative clears → 'clears'.
        r3 = self._run(_placed((1, "a"), (1, "b"), (1, "c")))
        self.assertGreaterEqual(r3["caterpillars_low"], BROOD_NEED_LOW)
        self.assertEqual(r3["status"], "clears")
        # 1 small host (3 species): 450–1,200 → optimistic under min → 'short'.
        rs = self._run(_placed((2, "Small Aster")))
        self.assertLess(rs["caterpillars_high"], BROOD_NEED_LOW)
        self.assertEqual(rs["status"], "short")

    def test_host_plants_ranked_and_shaped(self):
        r = self._run(_placed((2, "Small Aster"), (1, "Willow"), (9, "Sedge")))
        hp = r["host_plants"]
        # Sedge (rank 0) excluded; Willow ahead of Aster (richer keystone).
        self.assertEqual([h["common_name"] for h in hp], ["Willow", "Small Aster"])
        for h in hp:
            self.assertEqual(
                set(h),
                {"plant_id", "common_name", "count", "keystone_rank",
                 "caterpillars_low", "caterpillars_high"})
        self.assertEqual(r["brood_need_low"], BROOD_NEED_LOW)
        self.assertEqual(r["brood_need_high"], BROOD_NEED_HIGH)

    def test_reports_an_honest_range(self):
        r = self._run(_placed((1, "Willow"), (2, "Aster")))
        # A range, never a single fake number.
        self.assertLess(r["caterpillars_low"], r["caterpillars_high"])
        self.assertGreaterEqual(r["broods_high"], r["broods_low"])
        # Verdict cites the 6,000–9,000 need.
        self.assertIn("6,000", r["verdict"])
        self.assertIn("9,000", r["verdict"])


class TestChickadeeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_real_db_keystone_host(self):
        from src.db.fauna import keystone_rank_lepidoptera
        from src.db.plants import get_connection
        conn = get_connection()
        try:
            rows = conn.execute(
                """SELECT pf.plant_id, COUNT(DISTINCT pf.fauna_id) n
                   FROM plant_fauna pf JOIN fauna f ON f.id = pf.fauna_id
                   WHERE pf.relationship = 'larval_host'
                     AND f.taxon = 'lepidoptera'
                   GROUP BY pf.plant_id ORDER BY n DESC LIMIT 1""").fetchall()
        finally:
            conn.close()
        self.assertTrue(rows, "seed data should have a larval-host plant")
        pid = rows[0][0]
        self.assertGreater(keystone_rank_lepidoptera(pid), 0)
        # A big pile of the top keystone should at least reach 'partway'.
        placed = [{"plant_id": pid, "common_name": "Keystone"} for _ in range(5)]
        r = chickadee_provision(placed)
        self.assertIn(r["status"], ("partway", "clears"))
        self.assertGreater(r["caterpillars_high"], 0)
        self.assertGreater(r["n_host_species"], 0)

    def test_api_surface(self):
        import src.permadesign_api as api
        self.assertIn("chickadee_provision", api.__all__)
        self.assertTrue(hasattr(api, "chickadee_provision"))


if __name__ == "__main__":
    unittest.main()
