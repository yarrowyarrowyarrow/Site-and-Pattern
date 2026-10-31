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

    # The plant these tests lean on was "Yarrow" until V2.80 merged *Achillea
    # millefolium* into Boreal Yarrow (*A. borealis*). The seed data followed
    # the rename; these tests did not, and because a missing plant was a
    # `skipTest`, all three stopped testing anything on every machine for three
    # releases with the suite reading OK (found V2.83, fixed V2.84). A seeded
    # plant going missing is now a failure, which is what it always was.
    YARROW = "Boreal Yarrow"

    def _seeded_id(self, common_name: str) -> int:
        pid = self._plant_id_by_name(common_name)
        self.assertIsNotNone(
            pid, f"{common_name!r} is not in the seeded catalogue -- renamed? "
                 "src/db/seed_data.SEED_COMPANIONS names plants by common name")
        return pid

    def test_yarrow_has_seeded_friends(self):
        """SEED_COMPANIONS pairs Boreal Yarrow with Saskatoon Berry. Verifies
        the seed pipeline actually populated the table."""
        result = get_companions(self._seeded_id(self.YARROW))
        friend_names = {p.get("common_name") for p in result["friends"]}
        self.assertIn("Saskatoon Berry", friend_names)

    def test_relationships_are_bidirectional(self):
        """SEED_COMPANIONS lists each pair once; the query should return
        the relationship from either side."""
        yarrow_id = self._seeded_id(self.YARROW)
        sask_id = self._seeded_id("Saskatoon Berry")
        yarrow_friend_ids = {p["id"] for p in get_companions(yarrow_id)["friends"]}
        sask_friend_ids = {p["id"] for p in get_companions(sask_id)["friends"]}
        self.assertIn(sask_id, yarrow_friend_ids)
        self.assertIn(yarrow_id, sask_friend_ids,
                      "Companion relationships must be bidirectional")

    def test_returned_plants_have_expected_fields(self):
        """The detail-panel row reads `common_name`; verify it's present
        on every companion dict returned by the query."""
        result = get_companions(self._seeded_id(self.YARROW))
        self.assertTrue(result["friends"] + result["enemies"])
        for p in result["friends"] + result["enemies"]:
            self.assertIn("common_name", p)
            self.assertIn("id", p)


if __name__ == "__main__":
    unittest.main()
