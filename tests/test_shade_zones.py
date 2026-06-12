"""
tests/test_shade_zones.py

V1.53 / schema-v21 — the derived shade-tag cache (shade_zone_cache table +
src/db/shade_zones.py helpers). Uses the temp-DB pattern from
test_climate_cache.py so the real user DB stays untouched.
"""

import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_shadezone_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import init_db, get_connection, _SCHEMA_VERSION  # noqa: E402
import src.db.shade_zones as sz  # noqa: E402


class TestTagForFraction(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(sz.tag_for_fraction(0.0), "full_sun")
        self.assertEqual(sz.tag_for_fraction(0.14), "full_sun")
        self.assertEqual(sz.tag_for_fraction(0.15), "partial_shade")
        self.assertEqual(sz.tag_for_fraction(0.30), "partial_shade")
        self.assertEqual(sz.tag_for_fraction(0.39), "partial_shade")
        self.assertEqual(sz.tag_for_fraction(0.40), "full_shade")
        self.assertEqual(sz.tag_for_fraction(0.80), "full_shade")


class TestProjectKey(unittest.TestCase):
    def test_stable_and_pathlike(self):
        k1 = sz.project_key_for("/tmp/a/foo.perma.geojson")
        k2 = sz.project_key_for("/tmp/a/../a/foo.perma.geojson")
        self.assertEqual(k1, k2)              # normalized → same key
        self.assertNotEqual(k1, sz.project_key_for("/tmp/a/bar.perma.geojson"))

    def test_unsaved_sentinel(self):
        self.assertEqual(sz.project_key_for(None), "__unsaved__")


class TestShadeZoneCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.pk = sz.project_key_for("/tmp/proj/test.perma.geojson")
        sz.clear_zone_tags(self.pk)

    def test_schema_version_at_least_v21(self):
        self.assertGreaterEqual(_SCHEMA_VERSION, 21)

    def test_table_exists(self):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='shade_zone_cache'").fetchone()
            self.assertIsNotNone(row)
        finally:
            conn.close()

    def test_store_and_get_round_trip(self):
        rows = [
            {"zone_id": "r0c0", "shade_tag": "full_sun", "shade_frac": 0.05,
             "centroid_lat": 53.5, "centroid_lng": -113.5},
            {"zone_id": "r0c1", "shade_tag": "partial_shade", "shade_frac": 0.3},
            {"zone_id": "r1c0", "shade_tag": "full_shade", "shade_frac": 0.7},
        ]
        n = sz.store_zone_tags(self.pk, rows)
        self.assertEqual(n, 3)
        got = sz.get_zone_tags(self.pk)
        self.assertEqual(set(got), {"r0c0", "r0c1", "r1c0"})
        self.assertEqual(got["r0c0"]["shade_tag"], "full_sun")
        self.assertAlmostEqual(got["r1c0"]["shade_frac"], 0.7)

    def test_overwrite_same_zone(self):
        sz.store_zone_tags(self.pk, [
            {"zone_id": "r0c0", "shade_tag": "full_sun", "shade_frac": 0.0}])
        sz.store_zone_tags(self.pk, [
            {"zone_id": "r0c0", "shade_tag": "full_shade", "shade_frac": 0.9}])
        got = sz.get_zone_tags(self.pk)
        self.assertEqual(got["r0c0"]["shade_tag"], "full_shade")

    def test_clear_is_project_scoped(self):
        other = sz.project_key_for("/tmp/proj/other.perma.geojson")
        sz.store_zone_tags(self.pk, [
            {"zone_id": "z", "shade_tag": "full_sun"}])
        sz.store_zone_tags(other, [
            {"zone_id": "z", "shade_tag": "full_shade"}])
        sz.clear_zone_tags(self.pk)
        self.assertEqual(sz.get_zone_tags(self.pk), {})
        self.assertEqual(sz.get_zone_tags(other)["z"]["shade_tag"], "full_shade")
        sz.clear_zone_tags(other)

    def test_tag_counts(self):
        sz.store_zone_tags(self.pk, [
            {"zone_id": "a", "shade_tag": "full_sun"},
            {"zone_id": "b", "shade_tag": "full_sun"},
            {"zone_id": "c", "shade_tag": "partial_shade"},
        ])
        counts = sz.tag_counts(self.pk)
        self.assertEqual(counts["full_sun"], 2)
        self.assertEqual(counts["partial_shade"], 1)
        self.assertEqual(counts["full_shade"], 0)

    def test_invalid_tag_rejected(self):
        with self.assertRaises(ValueError):
            sz.store_zone_tags(self.pk, [
                {"zone_id": "x", "shade_tag": "bright"}])

    def test_check_constraint_at_db_level(self):
        # Bypass the helper's validation to prove the DB CHECK also guards.
        conn = get_connection()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO shade_zone_cache (project_key, zone_id, "
                    "shade_tag) VALUES (?, ?, ?)", (self.pk, "bad", "noon"))
                conn.commit()
        finally:
            conn.close()

    def test_has_tags(self):
        self.assertFalse(sz.has_tags(self.pk))
        sz.store_zone_tags(self.pk, [
            {"zone_id": "r0c0", "shade_tag": "full_sun"}])
        self.assertTrue(sz.has_tags(self.pk))

    def test_tag_at_nearest(self):
        sz.store_zone_tags(self.pk, [
            {"zone_id": "a", "shade_tag": "full_sun",
             "centroid_lat": 53.5000, "centroid_lng": -113.5000},
            {"zone_id": "b", "shade_tag": "full_shade",
             "centroid_lat": 53.5010, "centroid_lng": -113.5000},
        ])
        # Closer to 'a' → full_sun; closer to 'b' → full_shade.
        self.assertEqual(sz.tag_at(self.pk, 53.5001, -113.5000), "full_sun")
        self.assertEqual(sz.tag_at(self.pk, 53.5009, -113.5000), "full_shade")

    def test_tag_at_too_far_returns_none(self):
        sz.store_zone_tags(self.pk, [
            {"zone_id": "a", "shade_tag": "full_sun",
             "centroid_lat": 53.5000, "centroid_lng": -113.5000}])
        # ~1 km away, beyond the default 30 m match radius.
        self.assertIsNone(sz.tag_at(self.pk, 53.5090, -113.5000))

    def test_tag_at_empty_cache(self):
        self.assertIsNone(sz.tag_at(self.pk, 53.5, -113.5))

    def test_format_classification_status(self):
        counts = {"full_sun": 5, "partial_shade": 2, "full_shade": 1}
        s = sz.format_classification_status(8, counts)
        self.assertIn("8 spots", s)
        self.assertIn("5 full sun", s)
        self.assertNotIn("mismatch", s)
        s2 = sz.format_classification_status(8, counts, ["A wants X", "B wants Y"])
        self.assertIn("2 shade mismatch", s2)
        # More than 3 mismatches → truncates with a "+N more".
        s3 = sz.format_classification_status(
            8, counts, [f"w{i}" for i in range(5)])
        self.assertIn("+2 more", s3)


if __name__ == "__main__":
    unittest.main()
