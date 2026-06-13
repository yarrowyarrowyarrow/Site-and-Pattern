"""
tests/test_wind.py — seasonal wind rose + current wind (V1.67).

Headless stdlib unittest. The pure aggregation (compute_wind_rose,
wind_rose_geometry), the fetch parsing (network monkeypatched), and the
DB-cached summary (temp DB) — no Qt, no live network.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Redirect the DB to a temp dir before importing the cache helpers, so the
# cache test never touches the real user DB (mirrors test_polycultures).
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_wind_test_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")

from src import wind  # noqa: E402


def _rows(n, month, dir_deg, speed):
    return [{"month": month, "dir_deg": dir_deg, "speed": speed}
            for _ in range(n)]


class TestComputeWindRose(unittest.TestCase):

    def test_prevailing_and_bins(self):
        rows = _rows(100, 7, 0.0, 10.0)        # all N, 10 km/h, summer
        rose = wind.compute_wind_rose(rows)
        a = rose["annual"]
        self.assertEqual(a["n"], 100)
        self.assertEqual(a["prevailing_label"], "N")
        self.assertEqual(a["prevailing_deg"], 0.0)
        self.assertAlmostEqual(a["mean_speed"], 10.0)
        self.assertEqual(a["calm_pct"], 0.0)
        # 10 km/h falls in bin 1 (edges 5,12,20,30); N is dir index 0.
        self.assertAlmostEqual(a["matrix"][0][1], 100.0)
        self.assertEqual(sum(a["matrix"][0]), 100.0)

    def test_calm_fraction(self):
        rows = _rows(90, 7, 90.0, 15.0) + _rows(10, 7, 0.0, 1.0)  # 10 calm
        a = wind.compute_wind_rose(rows)["annual"]
        self.assertEqual(a["calm_pct"], 10.0)
        self.assertEqual(a["prevailing_label"], "E")   # the 90 non-calm are E

    def test_seasonal_split(self):
        rows = _rows(50, 1, 270.0, 20.0) + _rows(50, 7, 90.0, 8.0)
        rose = wind.compute_wind_rose(rows)
        self.assertEqual(rose["seasons"]["winter"]["n"], 50)
        self.assertEqual(rose["seasons"]["summer"]["n"], 50)
        self.assertEqual(rose["seasons"]["winter"]["prevailing_label"], "W")
        self.assertEqual(rose["seasons"]["spring"]["n"], 0)

    def test_empty(self):
        a = wind.compute_wind_rose([])["annual"]
        self.assertEqual(a["n"], 0)
        self.assertIsNone(a["prevailing_label"])


class TestDirHelpers(unittest.TestCase):
    def test_dir_index_and_label(self):
        self.assertEqual(wind.dir_label(0), "N")
        self.assertEqual(wind.dir_label(90), "E")
        self.assertEqual(wind.dir_label(180), "S")
        self.assertEqual(wind.dir_label(270), "W")
        self.assertEqual(wind.dir_label(359), "N")     # wraps

    def test_speed_category(self):
        self.assertEqual(wind.speed_category(3), "Light")
        self.assertEqual(wind.speed_category(15), "Moderate")
        self.assertEqual(wind.speed_category(40), "Very Strong")


class TestWindRoseGeometry(unittest.TestCase):
    def test_wedges_scaled_to_peak(self):
        block = wind._rose_block(
            _rows(50, 7, 0.0, 10.0) + _rows(25, 7, 180.0, 10.0))
        wedges = wind.wind_rose_geometry(block, max_radius=1.0)
        self.assertTrue(wedges)
        # Busiest direction (N) reaches max_radius; S is half.
        n_wedge = max((w for w in wedges if w["dir_index"] == 0),
                      key=lambda w: w["r1"])
        s_wedge = max((w for w in wedges if w["dir_index"] == 8),
                      key=lambda w: w["r1"])
        self.assertAlmostEqual(n_wedge["r1"], 1.0, places=3)
        self.assertAlmostEqual(s_wedge["r1"], 0.5, places=3)

    def test_empty_block_no_wedges(self):
        self.assertEqual(wind.wind_rose_geometry(wind._rose_block([])), [])


class TestFetchParsing(unittest.TestCase):
    def setUp(self):
        self._orig = wind._http_get_json

    def tearDown(self):
        wind._http_get_json = self._orig

    def test_fetch_historical_wind_parses(self):
        wind._http_get_json = lambda url, timeout=20.0: {"hourly": {
            "time": ["2023-01-01T00:00", "2023-07-15T12:00", "2023-07-15T13:00"],
            "wind_speed_10m": [10.0, None, 8.0],
            "wind_direction_10m": [0.0, 90.0, 90.0]}}
        rows = wind.fetch_historical_wind(53.5, -113.5)
        self.assertEqual(len(rows), 2)          # the None-speed row is dropped
        self.assertEqual(rows[0], {"month": 1, "speed": 10.0, "dir_deg": 0.0})
        self.assertEqual(rows[1]["month"], 7)

    def test_fetch_historical_wind_none_on_failure(self):
        wind._http_get_json = lambda url, timeout=20.0: None
        self.assertIsNone(wind.fetch_historical_wind(53.5, -113.5))

    def test_fetch_current_wind(self):
        wind._http_get_json = lambda url, timeout=12.0: {"current": {
            "wind_speed_10m": 12.3, "wind_direction_10m": 270.0,
            "wind_gusts_10m": 21.0}}
        cur = wind.fetch_current_wind(53.5, -113.5)
        self.assertEqual(cur["dir_label"], "W")
        self.assertEqual(cur["speed"], 12.3)
        self.assertEqual(cur["gusts"], 21.0)


class TestGetWindSummary(unittest.TestCase):
    def test_no_cache_path(self):
        rose = wind.get_wind_summary(
            53.5, -113.5, use_cache=False,
            _fetcher=lambda lat, lng: _rows(20, 7, 0.0, 10.0))
        self.assertFalse(rose["cached"])
        self.assertEqual(rose["annual"]["prevailing_label"], "N")

    def test_no_cache_failure_returns_none(self):
        self.assertIsNone(wind.get_wind_summary(
            53.5, -113.5, use_cache=False, _fetcher=lambda lat, lng: None))


class TestWindCacheDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()

    def test_store_and_get_roundtrip(self):
        from src.db.plants import get_cached_wind, store_cached_wind
        rose = wind.compute_wind_rose(_rows(30, 7, 90.0, 12.0))
        store_cached_wind(50.1, -110.2, rose)
        got = get_cached_wind(50.1, -110.2)
        self.assertEqual(got["annual"]["prevailing_label"], "E")
        self.assertIn("cached_at", got)
        self.assertIsNone(get_cached_wind(40.0, -120.0))   # miss

    def test_summary_uses_cache_second_time(self):
        calls = {"n": 0}

        def fetch(lat, lng):
            calls["n"] += 1
            return _rows(15, 1, 270.0, 18.0)

        first = wind.get_wind_summary(48.0, -114.0, _fetcher=fetch)
        self.assertFalse(first["cached"])
        second = wind.get_wind_summary(48.0, -114.0, _fetcher=fetch)
        self.assertTrue(second["cached"])
        self.assertEqual(calls["n"], 1)        # fetched once, then cached


if __name__ == "__main__":
    unittest.main()
