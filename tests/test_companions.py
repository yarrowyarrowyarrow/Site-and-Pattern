"""
tests/test_companions.py

Verifies the `get_companions(plant_id)` query layer used by the V1.33
plant-detail Companions row. The companion tables (`companion_friends`,
`companion_enemies`) are seeded at install from
`src/db/seed_data.py:SEED_COMPANIONS`; this test confirms the query
returns those seeded relationships bidirectionally and in a stable
shape.

Uses the same temp-DB pattern as `test_uses_junction.py` /
`test_fauna.py` so the real user DB is never touched.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_companions_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_connection,
    get_companions,
)


class TestGetCompanions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def _plant_id_by_name(self, common_name: str) -> int | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM plants WHERE common_name = ?",
                (common_name,),
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    # ── Shape of the returned dict ───────────────────────────────────────

    def test_returns_friends_and_enemies_keys(self):
        # Pick any plant id that exists — even one with no companions
        # should return the two keys with empty lists.
        conn = get_connection()
        try:
            row = conn.execute("SELECT id FROM plants LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, "Seeded DB should have at least one plant")
        result = get_companions(row[0])
        self.assertIn("friends", result)
        self.assertIn("enemies", result)
        self.assertIsInstance(result["friends"], list)
        self.assertIsInstance(result["enemies"], list)

    def test_unknown_plant_id_returns_empty_lists(self):
        result = get_companions(999_999)
        self.assertEqual(result, {"friends": [], "enemies": []})

    # ── Seeded relationships flow through correctly ──────────────────────

    def test_yarrow_has_seeded_friends(self):
        """Per seed_data.py, Yarrow is friends with several fruit trees.
        Verifies the seed pipeline actually populated the table."""
        yarrow_id = self._plant_id_by_name("Yarrow")
        if yarrow_id is None:
            self.skipTest("Yarrow not present in seeded plant data")
        result = get_companions(yarrow_id)
        friend_names = {p.get("common_name") for p in result["friends"]}
        # SEED_COMPANIONS lists Yarrow with Goodland Apple, Norland Apple,
        # Evans Cherry, Saskatoon Berry. We don't assert all four
        # (some may be filtered out if the seeded plants_master.json
        # doesn't include cultivars), but at least one must show through.
        seeded_yarrow_friends = {
            "Goodland Apple", "Norland Apple", "Evans Cherry", "Saskatoon Berry",
        }
        self.assertTrue(
            friend_names & seeded_yarrow_friends,
            f"Expected Yarrow's friends to include at least one of "
            f"{seeded_yarrow_friends}; got {friend_names}",
        )

    def test_relationships_are_bidirectional(self):
        """SEED_COMPANIONS lists each pair once; the query should return
        the relationship from either side."""
        yarrow_id = self._plant_id_by_name("Yarrow")
        sask_id   = self._plant_id_by_name("Saskatoon Berry")
        if yarrow_id is None or sask_id is None:
            self.skipTest("Yarrow or Saskatoon Berry not in seeded data")

        yarrow_friend_ids = {p["id"] for p in get_companions(yarrow_id)["friends"]}
        sask_friend_ids   = {p["id"] for p in get_companions(sask_id)["friends"]}

        # If Yarrow ↔ Saskatoon are seeded as friends, both sides see it.
        if sask_id in yarrow_friend_ids:
            self.assertIn(yarrow_id, sask_friend_ids,
                          "Companion relationships must be bidirectional")

    def test_returned_plants_have_expected_fields(self):
        """The detail-panel row reads `common_name`; verify it's present
        on every companion dict returned by the query."""
        yarrow_id = self._plant_id_by_name("Yarrow")
        if yarrow_id is None:
            self.skipTest("Yarrow not present in seeded plant data")
        result = get_companions(yarrow_id)
        for p in result["friends"] + result["enemies"]:
            self.assertIn("common_name", p)
            self.assertIn("id", p)


if __name__ == "__main__":
    unittest.main()
