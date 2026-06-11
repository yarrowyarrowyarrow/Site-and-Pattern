"""
tests/test_terrain_store.py

Coverage for src/terrain_store.py (Chunk 9 backfill). Two layers:

  • Pure tile-key geometry (_tile_key / _tiles_for_bbox /
    _tiles_touched_by_line) — no DB, deterministic.
  • The SRTM grid cache (store/get round-trip, miss returns None,
    overwrite) against a TEMP terrain.db so the real user cache at
    ~/.local/share/PermaDesign/terrain.db is never touched.

Qt-free. The temp DB is wired by monkeypatching the module's _db_path.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import src.terrain_store as ts  # noqa: E402
from src.terrain_store import (  # noqa: E402
    _tile_key,
    _tiles_for_bbox,
    _tiles_touched_by_line,
    TerrainStore,
)


class TestTileKeyGeometry(unittest.TestCase):
    """Pure functions — no DB."""

    def test_tile_key_format(self):
        # 0.01° cells: floor(lat*100)_floor(lng*100)
        self.assertEqual(_tile_key(53.5461, -113.4938), "5354_-11350")

    def test_tile_key_is_floor_based(self):
        # Negative longitudes floor downward (more negative).
        self.assertEqual(_tile_key(53.549, -113.491), "5354_-11350")
        self.assertEqual(_tile_key(53.540, -113.500), "5354_-11350")

    def test_tiles_for_bbox_single_cell(self):
        keys = _tiles_for_bbox(53.541, 53.549, -113.499, -113.491)
        self.assertEqual(keys, ["5354_-11350"])

    def test_tiles_for_bbox_grid(self):
        # A bbox spanning 2 lat cells × 2 lng cells → 4 tiles.
        keys = _tiles_for_bbox(53.54, 53.55, -113.50, -113.49)
        self.assertEqual(len(keys), 4)
        self.assertEqual(len(set(keys)), 4)   # all distinct

    def test_tiles_touched_by_line_endpoints(self):
        # A short line within one cell touches just that cell.
        touched = _tiles_touched_by_line([[53.541, -113.499], [53.549, -113.491]])
        self.assertEqual(touched, {"5354_-11350"})

    def test_tiles_touched_by_line_crosses_cells(self):
        # A line spanning multiple cells touches the intermediate tiles
        # (the 0.005° stepping must not skip any).
        touched = _tiles_touched_by_line([[53.50, -113.50], [53.55, -113.50]])
        # 53.50→53.55 crosses lat cells 5350..5355 at fixed lng cell.
        self.assertIn("5350_-11350", touched)
        self.assertIn("5355_-11350", touched)
        # Contiguous: every lat cell between is present.
        lat_cells = sorted(int(k.split("_")[0]) for k in touched)
        self.assertEqual(lat_cells, list(range(min(lat_cells), max(lat_cells) + 1)))

    def test_tiles_touched_by_empty_line(self):
        self.assertEqual(_tiles_touched_by_line([]), set())


class TestSrtmCache(unittest.TestCase):
    """SRTM grid cache hit/miss against a temp terrain.db."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="permadesign_terrain_store_")
        self._db = os.path.join(self._tmp, "terrain.db")
        self._patch = mock.patch.object(ts, "_db_path", return_value=self._db)
        self._patch.start()
        self.store = TerrainStore()

    def tearDown(self):
        self._patch.stop()

    def test_miss_returns_none(self):
        self.assertIsNone(self.store.get_srtm_grid("nonexistent-key"))

    def test_store_then_hit_round_trips(self):
        grid = {"elevations": [[1.0, 2.0], [3.0, 4.0]], "rows": 2, "cols": 2}
        self.store.store_srtm_grid("k1", grid)
        got = self.store.get_srtm_grid("k1")
        self.assertEqual(got, grid)

    def test_store_compresses_and_survives_reopen(self):
        grid = {"elevations": [[float(i)] for i in range(100)]}
        self.store.store_srtm_grid("big", grid)
        # A fresh store instance reads the same on-disk cache.
        other = TerrainStore()
        self.assertEqual(other.get_srtm_grid("big"), grid)

    def test_overwrite_replaces(self):
        self.store.store_srtm_grid("k", {"v": 1})
        self.store.store_srtm_grid("k", {"v": 2})
        self.assertEqual(self.store.get_srtm_grid("k"), {"v": 2})

    def test_edmonton_feature_count_starts_zero(self):
        # Fresh DB → no Edmonton tiles loaded yet.
        self.assertEqual(self.store.get_edmonton_feature_count(), 0)

    def test_does_not_touch_real_user_db(self):
        # The patched path must be our temp file, not the real cache.
        self.assertTrue(self._db.startswith(self._tmp))
        self.store.store_srtm_grid("x", {"a": 1})
        self.assertTrue(os.path.exists(self._db))


class TestDbPathPlatforms(unittest.TestCase):
    """_db_path resolves the platform-correct per-user data directory.

    os.name / sys.platform / env vars are patched so all three branches
    are exercised regardless of the host OS; os.makedirs is stubbed so no
    real directories are created.
    """

    def test_windows_uses_appdata(self):
        appdata = os.path.join("C:", "Users", "x", "AppData", "Roaming")
        with mock.patch.object(os, "name", "nt"), \
             mock.patch.dict(os.environ, {"APPDATA": appdata}), \
             mock.patch.object(os, "makedirs"):
            path = ts._db_path()
        self.assertEqual(path, os.path.join(appdata, "PermaDesign", "terrain.db"))

    def test_macos_uses_application_support(self):
        with mock.patch.object(os, "name", "posix"), \
             mock.patch.object(sys, "platform", "darwin"), \
             mock.patch.object(os, "makedirs"):
            path = ts._db_path()
        expected = os.path.join(os.path.expanduser("~"),
                                "Library", "Application Support",
                                "PermaDesign", "terrain.db")
        self.assertEqual(path, expected)

    def test_linux_uses_xdg_data_home(self):
        with mock.patch.object(os, "name", "posix"), \
             mock.patch.object(sys, "platform", "linux"), \
             mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-test"}), \
             mock.patch.object(os, "makedirs"):
            path = ts._db_path()
        self.assertEqual(path, os.path.join("/tmp/xdg-test",
                                            "PermaDesign", "terrain.db"))


if __name__ == "__main__":
    unittest.main()
