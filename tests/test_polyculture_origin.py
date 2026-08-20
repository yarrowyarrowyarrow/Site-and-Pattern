"""
tests/test_polyculture_origin.py — user communities survive the reseed
(schema v46).

Before v46 the schema-bump reseed ran ``DELETE FROM polycultures``, which
destroyed every community a user had authored in the builder — on every
release. These tests pin the fix:

  * the seeder stamps its rows ``origin='seed'``; the builder default is
    ``'user'``,
  * a version-bump reseed wipes + re-seeds ONLY the examples; user rows
    (and their members) survive, without duplicating the examples,
  * user members are re-pointed at the reseeded plant rows by name
    (plant ids shift on every reseed — AUTOINCREMENT is never reset),
  * the v45→v46 upgrade path itself (column added, examples re-stamped by
    name, no duplicates after the first v46 reseed).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_origin_test_")
import src.db.plants as _plants_mod              # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (                      # noqa: E402
    _SCHEMA_VERSION, get_connection, init_db,
)
from src.db import polycultures                  # noqa: E402


def _force_reseed():
    """Rewind the stored schema version so the next init_db reseeds."""
    conn = get_connection()
    try:
        conn.execute("UPDATE _schema_version SET version = ?",
                     (_SCHEMA_VERSION - 1,))
        conn.commit()
    finally:
        conn.close()
    init_db()


def _seed_count(conn):
    return conn.execute("SELECT COUNT(*) FROM polycultures "
                        "WHERE origin='seed'").fetchone()[0]


class TestUserPolyculturesSurviveReseed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def _any_two_plants(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, common_name, scientific_name FROM plants "
                "ORDER BY id LIMIT 2").fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def test_examples_are_stamped_seed_and_builder_default_is_user(self):
        conn = get_connection()
        try:
            self.assertGreater(_seed_count(conn), 0,
                               "examples should be seeded as origin='seed'")
        finally:
            conn.close()
        pid = polycultures.create_polyculture("Origin Default Probe", "", None)
        try:
            conn = get_connection()
            try:
                origin = conn.execute(
                    "SELECT origin FROM polycultures WHERE id=?",
                    (pid,)).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(origin, "user")
        finally:
            polycultures.delete_polyculture(pid)

    def test_user_community_survives_reseed_with_members_remapped(self):
        plants = self._any_two_plants()
        pid = polycultures.create_polyculture(
            "Aurianna's Test Guild", "user-authored", plants[0]["id"])
        polycultures.add_polyculture_member(
            pid, plants[0]["id"], "overstory", 0.0, 0.0)
        polycultures.add_polyculture_member(
            pid, plants[1]["id"], "groundcover", 1.0, 1.0)

        conn = get_connection()
        try:
            examples_before = _seed_count(conn)
        finally:
            conn.close()

        _force_reseed()

        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT id, origin, center_plant_id FROM polycultures "
                "WHERE name=?", ("Aurianna's Test Guild",)).fetchone()
            self.assertIsNotNone(row, "user community wiped by reseed!")
            self.assertEqual(row["origin"], "user")

            members = conn.execute(
                "SELECT pm.plant_id, p.common_name FROM polyculture_members pm "
                "JOIN plants p ON p.id = pm.plant_id "
                "WHERE pm.polyculture_id=?", (row["id"],)).fetchall()
            self.assertEqual(len(members), 2,
                             "user members lost or orphaned across reseed")
            names = {m["common_name"] for m in members}
            self.assertEqual(
                names, {plants[0]["common_name"], plants[1]["common_name"]},
                "members must be re-pointed at the same species by name")
            # The center plant must also resolve inside the fresh catalogue.
            center = conn.execute(
                "SELECT common_name FROM plants WHERE id=?",
                (row["center_plant_id"],)).fetchone()
            self.assertIsNotNone(center)
            self.assertEqual(center["common_name"], plants[0]["common_name"])

            self.assertEqual(_seed_count(conn), examples_before,
                             "examples must be re-seeded once, not duplicated")
        finally:
            conn.close()
            polycultures.delete_polyculture(row["id"])

    def test_v45_to_v46_upgrade_restamps_examples_without_duplicates(self):
        # Simulate a pre-v46 DB: drop the origin column (SQLite ≥3.35) and
        # rewind the version, then run the real upgrade path.
        conn = get_connection()
        try:
            names_before = {r[0] for r in conn.execute(
                "SELECT name FROM polycultures WHERE origin='seed'")}
            conn.execute("ALTER TABLE polycultures DROP COLUMN origin")
            conn.execute("UPDATE _schema_version SET version = 45")
            conn.commit()
        finally:
            conn.close()

        # Insert a "legacy" user community directly (no origin column now).
        conn = get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO polycultures (name, description) "
                "VALUES ('Legacy User Guild', 'pre-v46 row')")
            legacy_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()

        init_db()   # runs _migrate_to_v46 + the v46 reseed

        conn = get_connection()
        try:
            # Legacy user row survived and was classified 'user'.
            row = conn.execute(
                "SELECT origin FROM polycultures WHERE name=?",
                ("Legacy User Guild",)).fetchone()
            self.assertIsNotNone(row, "legacy user community lost on upgrade")
            self.assertEqual(row["origin"], "user")
            # Examples present exactly once each (re-stamped, wiped, re-seeded).
            dupes = conn.execute(
                "SELECT name, COUNT(*) c FROM polycultures "
                "GROUP BY name HAVING c > 1").fetchall()
            self.assertFalse([tuple(d) for d in dupes],
                             "upgrade must not duplicate shipped examples")
            names_after = {r[0] for r in conn.execute(
                "SELECT name FROM polycultures WHERE origin='seed'")}
            self.assertEqual(names_before, names_after)
            legacy = conn.execute(
                "SELECT id FROM polycultures WHERE name='Legacy User Guild'"
            ).fetchone()
        finally:
            conn.close()
        polycultures.delete_polyculture(legacy["id"])


if __name__ == "__main__":
    unittest.main()
