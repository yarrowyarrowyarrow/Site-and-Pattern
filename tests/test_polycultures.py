"""
tests/test_polycultures.py

Unit tests for src/db/polycultures.py covering the crash scenarios:
  1. create_polyculture writes to DB and returns an int ID
  2. add_polyculture_member rejects plant_id=None with ValueError
  3. add_polyculture_member works with a real plant_id
  4. delete_polyculture removes polyculture and its members
  5. duplicate_polyculture copies all members
  6. remove_polyculture_member removes one row and leaves others
  7. Readonly DB raises an informative exception (not a silent hang)
  8. DB is stored in the user-data dir, not next to the source tree
"""

import os
import pathlib
import sqlite3
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Redirect the DB to a temp directory so tests never touch the real user DB
# ---------------------------------------------------------------------------
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_test_")

import importlib
import src.db.plants as _plants_mod

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

# Now safe to import polycultures (it calls get_connection which uses the patched paths)
from src.db import polycultures
from src.db.plants import init_db, get_connection


def _setup_db():
    """Initialise schema + seed data in the temp DB."""
    init_db()


def _add_dummy_plant(conn, name="Test Plant", ptype="herb"):
    cur = conn.execute(
        "INSERT INTO plants (common_name, plant_type) VALUES (?, ?)",
        (name, ptype),
    )
    conn.commit()
    return cur.lastrowid


class TestPolycultureCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _setup_db()

    def setUp(self):
        # Clean polyculture tables before each test so tests are independent
        conn = get_connection()
        conn.execute("DELETE FROM polyculture_members")
        conn.execute("DELETE FROM polycultures")
        conn.commit()
        conn.close()

    # ── create_polyculture ──────────────────────────────────────────────────────────

    def test_create_polyculture_returns_int(self):
        gid = polycultures.create_polyculture("Test Polyculture", "A description", None)
        self.assertIsInstance(gid, int)
        self.assertGreater(gid, 0)

    def test_create_polyculture_persists(self):
        polycultures.create_polyculture("Persisted", "", None)
        rows = polycultures.get_all_polycultures()
        names = [r["name"] for r in rows]
        self.assertIn("Persisted", names)

    def test_create_polyculture_with_parent(self):
        parent_id = polycultures.create_polyculture("Parent", "", None)
        child_id  = polycultures.create_polyculture("Child", "", None, parent_id=parent_id)
        children = polycultures.get_polyculture_children(parent_id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["id"], child_id)

    # ── add_polyculture_member ─────────────────────────────────────────────────────

    def test_add_member_none_plant_id_raises(self):
        gid = polycultures.create_polyculture("G", "", None)
        with self.assertRaises(ValueError):
            polycultures.add_polyculture_member(gid, None, "canopy", 0, 0)

    def test_add_member_invalid_plant_id_raises(self):
        """Foreign-key violation (plant doesn't exist) must raise, not silently pass."""
        gid = polycultures.create_polyculture("G2", "", None)
        with self.assertRaises(Exception):
            polycultures.add_polyculture_member(gid, 999999, "canopy", 0.5, -0.5)

    def test_add_member_valid(self):
        conn = get_connection()
        plant_id = _add_dummy_plant(conn, "Stinging Nettle")
        conn.close()

        gid = polycultures.create_polyculture("Apple Polyculture", "", None)
        polycultures.add_polyculture_member(gid, plant_id, "dynamic_accumulator", 1.5, 0.8)

        detail = polycultures.get_polyculture_by_id(gid)
        self.assertEqual(len(detail["members"]), 1)
        self.assertEqual(detail["members"][0]["common_name"], "Stinging Nettle")

    # ── remove_polyculture_member ──────────────────────────────────────────────────

    def test_remove_member(self):
        conn = get_connection()
        pid1 = _add_dummy_plant(conn, "PlantA")
        pid2 = _add_dummy_plant(conn, "PlantB")
        conn.close()

        gid = polycultures.create_polyculture("G3", "", None)
        polycultures.add_polyculture_member(gid, pid1, "canopy", 0, 0)
        polycultures.add_polyculture_member(gid, pid2, "understory", 1, 0)

        detail = polycultures.get_polyculture_by_id(gid)
        member_id = detail["members"][0]["id"]
        polycultures.remove_polyculture_member(member_id)

        detail2 = polycultures.get_polyculture_by_id(gid)
        self.assertEqual(len(detail2["members"]), 1)

    # ── delete_polyculture ─────────────────────────────────────────────────────────

    def test_delete_polyculture_removes_members(self):
        conn = get_connection()
        pid = _add_dummy_plant(conn, "PlantC")
        conn.close()

        gid = polycultures.create_polyculture("ToDelete", "", None)
        polycultures.add_polyculture_member(gid, pid, "canopy", 0, 0)
        polycultures.delete_polyculture(gid)

        self.assertIsNone(polycultures.get_polyculture_by_id(gid))
        # Confirm no orphan members
        conn = get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM polyculture_members WHERE polyculture_id = ?", (gid,)
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    # ── duplicate_polyculture ──────────────────────────────────────────────────────

    def test_duplicate_polyculture_copies_members(self):
        conn = get_connection()
        pid = _add_dummy_plant(conn, "PlantD")
        conn.close()

        orig = polycultures.create_polyculture("Original", "desc", None)
        polycultures.add_polyculture_member(orig, pid, "pollinator", 0.5, 0.5)

        copy_id = polycultures.duplicate_polyculture(orig)
        copy = polycultures.get_polyculture_by_id(copy_id)
        self.assertEqual(len(copy["members"]), 1)
        self.assertIn("copy", copy["name"])

    def test_duplicate_as_variation(self):
        gid = polycultures.create_polyculture("Base", "", None)
        var_id = polycultures.duplicate_polyculture(gid, as_variation=True)
        children = polycultures.get_polyculture_children(gid)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["id"], var_id)

    # ── DB path ──────────────────────────────────────────────────────────────

    def test_db_not_in_source_tree(self):
        """The live DB must not live inside the PermaDesign source directory."""
        from src.db.plants import _DB_PATH, _PROJECT_ROOT
        db = pathlib.Path(_DB_PATH).resolve()
        src = pathlib.Path(_PROJECT_ROOT).resolve()
        self.assertFalse(
            db.is_relative_to(src),
            f"DB is inside the source tree: {db}",
        )

    # ── Readonly DB ──────────────────────────────────────────────────────────

    @unittest.skipIf(sys.platform == "win32", "chmod read-only unreliable on Windows CI")
    @unittest.skipIf(getattr(os, "getuid", lambda: -1)() == 0, "root ignores file permissions")
    def test_readonly_db_raises_not_silently_fails(self):
        """If the DB is read-only, create_polyculture must raise (not hang or return None)."""
        db_path = _plants_mod._DB_PATH
        original_mode = os.stat(db_path).st_mode
        try:
            os.chmod(db_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            with self.assertRaises(Exception):
                polycultures.create_polyculture("ShouldFail", "", None)
        finally:
            os.chmod(db_path, original_mode)


class TestStarterCommunities(unittest.TestCase):
    """P1 — the lawn-to-habitat starter communities seed with every member
    resolved (guards against the member-name drift the legacy food-forest
    presets suffer from)."""

    STARTERS = (
        "Boulevard Pollinator Strip",
        "Backyard Meadow Patch",
        "Hedgerow Shelterbelt",
    )

    @classmethod
    def setUpClass(cls):
        _setup_db()
        # Other test classes share this temp DB and create polycultures, so the
        # one-shot seed (which only runs on an empty table) may have been
        # skipped. Wipe + re-seed to guarantee a clean starter set here.
        conn = get_connection()
        conn.execute("DELETE FROM polyculture_members")
        conn.execute("DELETE FROM polycultures")
        conn.commit()
        conn.close()
        polycultures.seed_example_polycultures()

    def test_starters_seed_with_all_members(self):
        conn = get_connection()
        try:
            for name in self.STARTERS:
                pc = polycultures.get_polyculture_by_name(name)
                self.assertIsNotNone(pc, f"{name} not seeded")
                n = conn.execute(
                    "SELECT COUNT(*) FROM polyculture_members WHERE polyculture_id=?",
                    (pc["id"],)).fetchone()[0]
                # each starter defines six members; all must resolve to real
                # catalogue rows (0 silently-skipped names)
                self.assertEqual(n, 6, f"{name} resolved {n}/6 members")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
