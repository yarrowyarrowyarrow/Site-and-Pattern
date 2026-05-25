"""
tests/test_uses_junction.py

Verifies the schema v13 / V1.31 migration of the comma-delimited
``plants.permaculture_uses`` blob into the normalized ``uses`` lookup +
``plant_uses`` junction tables.

Each test runs against a fresh temp DB so we never touch the real user data.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp directory before importing anything that opens it.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_uses_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_connection,
    get_plant_uses,
    plants_with_use,
    plant_uses_for_ids,
    search_plants,
    _USE_DEFINITIONS,
)


class TestUsesJunction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    # ── Lookup table ────────────────────────────────────────────────────

    def test_uses_lookup_populated(self):
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM uses").fetchone()[0]
        finally:
            conn.close()
        # Should at least equal the number of canonical definitions.
        self.assertGreaterEqual(n, len(_USE_DEFINITIONS))

    def test_uses_lookup_has_canonical_keys(self):
        conn = get_connection()
        try:
            keys = {r[0] for r in conn.execute("SELECT key FROM uses").fetchall()}
        finally:
            conn.close()
        # Sample a handful of the highest-stakes ecological tags.
        for key in ("keystone_species", "host_plant", "bird_food",
                    "pollinator", "nitrogen_fixer"):
            self.assertIn(key, keys, f"Missing canonical use key: {key}")

    # ── Junction population ─────────────────────────────────────────────

    def test_plant_uses_populated_from_seed(self):
        conn = get_connection()
        try:
            n = conn.execute("SELECT COUNT(*) FROM plant_uses").fetchone()[0]
        finally:
            conn.close()
        # Conservative lower bound: at least one tag per plant on average.
        self.assertGreater(n, 400)

    def test_plant_uses_matches_legacy_column(self):
        """For every plant, the junction tag set must match the tokens in
        the legacy ``permaculture_uses`` string (filtered to canonical
        tokens that exist in the ``uses`` lookup)."""
        conn = get_connection()
        try:
            uses_keys = {
                r[0] for r in conn.execute("SELECT key FROM uses").fetchall()
            }
            rows = conn.execute(
                "SELECT id, permaculture_uses FROM plants "
                "WHERE permaculture_uses IS NOT NULL "
                "  AND permaculture_uses != '' LIMIT 50"
            ).fetchall()
        finally:
            conn.close()
        for pid, blob in rows:
            legacy_tokens = {
                t.strip() for t in (blob or "").split(",") if t.strip()
            }
            legacy_canonical = legacy_tokens & uses_keys
            junction = set(get_plant_uses(pid))
            self.assertEqual(
                legacy_canonical, junction,
                f"plant_id={pid}: legacy={legacy_canonical} junction={junction}",
            )

    # ── Query helpers ───────────────────────────────────────────────────

    def test_plants_with_use_keystone_is_non_empty(self):
        ids = plants_with_use("keystone_species")
        self.assertGreater(len(ids), 0)

    def test_plant_uses_for_ids_bulk(self):
        # Pick plants that we know have uses (real seeded natives, not the
        # bare dummy plants other test modules insert).
        conn = get_connection()
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT pu.plant_id FROM plant_uses pu LIMIT 5"
            ).fetchall()]
        finally:
            conn.close()
        self.assertGreater(len(ids), 0)
        bulk = plant_uses_for_ids(ids)
        # Contract: returned keys are a subset of the input ids, and every
        # plant we queried (all of which have uses) must appear with a
        # non-empty set.
        self.assertLessEqual(set(bulk.keys()), set(ids))
        for pid in ids:
            self.assertIn(pid, bulk)
            self.assertGreater(len(bulk[pid]), 0)

    # ── search_plants() — filters now go through the junction ────────────

    def test_search_keystone_only_uses_junction(self):
        results = search_plants(keystone_only=True)
        keystone_ids = plants_with_use("keystone_species")
        result_ids = {r["id"] for r in results}
        self.assertEqual(result_ids, keystone_ids)

    def test_search_host_plant_only_matches_legacy_set(self):
        """Reading via the junction must yield the same plant set as the
        legacy substring filter (because we still populate both during
        seed). This is the safety-net invariant."""
        new_results = {r["id"] for r in search_plants(host_plant_only=True)}
        conn = get_connection()
        try:
            legacy = {
                r[0] for r in conn.execute(
                    "SELECT id FROM plants "
                    "WHERE LOWER(permaculture_uses) LIKE '%host_plant%'"
                ).fetchall()
            }
        finally:
            conn.close()
        self.assertEqual(new_results, legacy)

    def test_search_bird_food_matches_legacy_set(self):
        new_results = {r["id"] for r in search_plants(bird_food_only=True)}
        conn = get_connection()
        try:
            legacy = {
                r[0] for r in conn.execute(
                    "SELECT id FROM plants "
                    "WHERE LOWER(permaculture_uses) LIKE '%bird_food%'"
                ).fetchall()
            }
        finally:
            conn.close()
        self.assertEqual(new_results, legacy)


if __name__ == "__main__":
    unittest.main()
