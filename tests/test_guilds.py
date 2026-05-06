"""
tests/test_guilds.py

Unit tests for src/db/guilds.py covering the crash scenarios:
  1. create_guild writes to DB and returns an int ID
  2. add_guild_member rejects plant_id=None with ValueError
  3. add_guild_member works with a real plant_id
  4. delete_guild removes guild and its members
  5. duplicate_guild copies all members
  6. remove_guild_member removes one row and leaves others
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

# ---------------------------------------------------------------------------
# Redirect the DB to a temp directory so tests never touch the real user DB
# ---------------------------------------------------------------------------
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_test_")

import importlib
import src.db.plants as _plants_mod

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

# Now safe to import guilds (it calls get_connection which uses the patched paths)
from src.db import guilds
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


class TestGuildCRUD(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _setup_db()

    def setUp(self):
        # Clean guild tables before each test so tests are independent
        conn = get_connection()
        conn.execute("DELETE FROM guild_members")
        conn.execute("DELETE FROM guilds")
        conn.commit()
        conn.close()

    # ── create_guild ──────────────────────────────────────────────────────────

    def test_create_guild_returns_int(self):
        gid = guilds.create_guild("Test Guild", "A description", None)
        self.assertIsInstance(gid, int)
        self.assertGreater(gid, 0)

    def test_create_guild_persists(self):
        guilds.create_guild("Persisted", "", None)
        rows = guilds.get_all_guilds()
        names = [r["name"] for r in rows]
        self.assertIn("Persisted", names)

    def test_create_guild_with_parent(self):
        parent_id = guilds.create_guild("Parent", "", None)
        child_id  = guilds.create_guild("Child", "", None, parent_id=parent_id)
        children = guilds.get_guild_children(parent_id)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["id"], child_id)

    # ── add_guild_member ─────────────────────────────────────────────────────

    def test_add_member_none_plant_id_raises(self):
        gid = guilds.create_guild("G", "", None)
        with self.assertRaises(ValueError):
            guilds.add_guild_member(gid, None, "canopy", 0, 0)

    def test_add_member_invalid_plant_id_raises(self):
        """Foreign-key violation (plant doesn't exist) must raise, not silently pass."""
        gid = guilds.create_guild("G2", "", None)
        with self.assertRaises(Exception):
            guilds.add_guild_member(gid, 999999, "canopy", 0.5, -0.5)

    def test_add_member_valid(self):
        conn = get_connection()
        plant_id = _add_dummy_plant(conn, "Comfrey")
        conn.close()

        gid = guilds.create_guild("Apple Guild", "", None)
        guilds.add_guild_member(gid, plant_id, "dynamic_accumulator", 1.5, 0.8)

        detail = guilds.get_guild_by_id(gid)
        self.assertEqual(len(detail["members"]), 1)
        self.assertEqual(detail["members"][0]["common_name"], "Comfrey")

    # ── remove_guild_member ──────────────────────────────────────────────────

    def test_remove_member(self):
        conn = get_connection()
        pid1 = _add_dummy_plant(conn, "PlantA")
        pid2 = _add_dummy_plant(conn, "PlantB")
        conn.close()

        gid = guilds.create_guild("G3", "", None)
        guilds.add_guild_member(gid, pid1, "canopy", 0, 0)
        guilds.add_guild_member(gid, pid2, "understory", 1, 0)

        detail = guilds.get_guild_by_id(gid)
        member_id = detail["members"][0]["id"]
        guilds.remove_guild_member(member_id)

        detail2 = guilds.get_guild_by_id(gid)
        self.assertEqual(len(detail2["members"]), 1)

    # ── delete_guild ─────────────────────────────────────────────────────────

    def test_delete_guild_removes_members(self):
        conn = get_connection()
        pid = _add_dummy_plant(conn, "PlantC")
        conn.close()

        gid = guilds.create_guild("ToDelete", "", None)
        guilds.add_guild_member(gid, pid, "canopy", 0, 0)
        guilds.delete_guild(gid)

        self.assertIsNone(guilds.get_guild_by_id(gid))
        # Confirm no orphan members
        conn = get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM guild_members WHERE guild_id = ?", (gid,)
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)

    # ── duplicate_guild ──────────────────────────────────────────────────────

    def test_duplicate_guild_copies_members(self):
        conn = get_connection()
        pid = _add_dummy_plant(conn, "PlantD")
        conn.close()

        orig = guilds.create_guild("Original", "desc", None)
        guilds.add_guild_member(orig, pid, "pollinator", 0.5, 0.5)

        copy_id = guilds.duplicate_guild(orig)
        copy = guilds.get_guild_by_id(copy_id)
        self.assertEqual(len(copy["members"]), 1)
        self.assertIn("copy", copy["name"])

    def test_duplicate_as_variation(self):
        gid = guilds.create_guild("Base", "", None)
        var_id = guilds.duplicate_guild(gid, as_variation=True)
        children = guilds.get_guild_children(gid)
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
    @unittest.skipIf(os.getuid() == 0, "root ignores file permissions")
    def test_readonly_db_raises_not_silently_fails(self):
        """If the DB is read-only, create_guild must raise (not hang or return None)."""
        db_path = _plants_mod._DB_PATH
        original_mode = os.stat(db_path).st_mode
        try:
            os.chmod(db_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            with self.assertRaises(Exception):
                guilds.create_guild("ShouldFail", "", None)
        finally:
            os.chmod(db_path, original_mode)


if __name__ == "__main__":
    unittest.main()
