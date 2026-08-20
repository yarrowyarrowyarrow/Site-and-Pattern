"""
tests/test_plant_cache.py — the in-memory plant-catalogue cache (V2.22).

get_plant() used to open a connection + run two queries per call, per
placed plant, per render. These tests pin the cache's contract:

  * get_plant serves from the cache and matches the uncached read API,
  * every write path (marker colour here; init_db/reseed by construction)
    invalidates, so readers never see stale rows,
  * callers get a defensive copy — mutating a result can't poison the
    cache for the next caller.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_cache_test_")
import src.db.plants as plants_mod              # noqa: E402
plants_mod._DATA_DIR = _TMP_DIR
plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (                     # noqa: E402
    get_all_plants, get_plant, init_db, update_marker_color,
)


class TestPlantCache(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.sample = get_all_plants()[0]

    def test_cached_read_matches_catalogue(self):
        p = get_plant(self.sample["id"])
        self.assertIsNotNone(p)
        self.assertEqual(p["common_name"], self.sample["common_name"])
        self.assertEqual(p["permaculture_uses"],
                         self.sample["permaculture_uses"],
                         "junction-synthesized field must survive caching")
        self.assertIsNotNone(plants_mod._plant_cache,
                             "first get_plant should populate the cache")

    def test_unknown_and_garbage_ids(self):
        self.assertIsNone(get_plant(99999999))
        self.assertIsNone(get_plant(None))
        self.assertIsNone(get_plant("not-an-id"))

    def test_marker_color_write_invalidates(self):
        pid = self.sample["id"]
        get_plant(pid)                            # warm the cache
        update_marker_color(pid, "#123456")
        try:
            self.assertEqual(get_plant(pid)["marker_color"], "#123456",
                             "stale cache served after a write")
        finally:
            update_marker_color(pid, None)
        self.assertFalse(get_plant(pid)["marker_color"])

    def test_returned_dict_is_a_defensive_copy(self):
        pid = self.sample["id"]
        p1 = get_plant(pid)
        p1["common_name"] = "POISONED"
        self.assertEqual(get_plant(pid)["common_name"],
                         self.sample["common_name"])


if __name__ == "__main__":
    unittest.main()
