"""
tests/test_climate_cache.py

Verifies the V1.35 / schema-v14 `climate_cache` table and its
`get_cached_climate` / `store_cached_climate` helpers in
`src/db/plants.py`. Uses the temp-DB pattern from
`test_uses_junction.py` so the real user DB stays untouched.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_climate_test_")

import src.db.plants as _plants_mod  # noqa: E402

_plants_mod._DATA_DIR = _TMP_DIR
_plants_mod._DB_PATH  = os.path.join(_TMP_DIR, "permadesign_test.db")

from src.db.plants import (  # noqa: E402
    init_db,
    get_cached_climate,
    store_cached_climate,
    _quantize_latlng,
    _SCHEMA_VERSION,
)


class TestClimateCache(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_schema_version_at_least_v14(self):
        """V1.35 introduced schema v14. Subsequent releases may bump
        further (V1.37 → v15 for the uses vocabulary refresh); the
        invariant we care about is that climate_cache exists, which
        is true from v14 onward."""
        self.assertGreaterEqual(_SCHEMA_VERSION, 14)

    def test_quantize_latlng(self):
        """0.01° granularity → multiplying by 100 and rounding."""
        self.assertEqual(_quantize_latlng(53.5462, -113.4938), (5355, -11349))
        # Symmetric: small displacements *within the same* 0.01° cell
        # land on the same key. Both lng values here round to -11349.
        self.assertEqual(
            _quantize_latlng(53.5462, -113.4938),
            _quantize_latlng(53.5471, -113.4940),
        )

    def test_miss_returns_none(self):
        # A location nobody's stored yet → None.
        self.assertIsNone(get_cached_climate(0.0, 0.0))

    def test_store_and_retrieve_round_trip(self):
        summary = {
            "gdd5_mean": 1420.5,
            "last_spring_frost_doy": 135,
            "first_fall_frost_doy":  265,
            "frost_free_days":       130,
            "years_used":            5,
            "source":                "Open-Meteo / ERA5-Land",
        }
        store_cached_climate(53.5462, -113.4938, summary)
        got = get_cached_climate(53.5462, -113.4938)
        self.assertIsNotNone(got)
        self.assertAlmostEqual(got["gdd5_mean"], 1420.5)
        self.assertEqual(got["last_spring_frost_doy"], 135)
        self.assertEqual(got["first_fall_frost_doy"], 265)
        self.assertEqual(got["frost_free_days"], 130)
        self.assertEqual(got["years_used"], 5)
        self.assertEqual(got["source"], "Open-Meteo / ERA5-Land")
        # cached_at timestamp is set automatically by SQLite — just
        # confirm it's present and non-empty.
        self.assertTrue(got.get("cached_at"))

    def test_store_overwrites_existing(self):
        loc = (45.0, -75.0)
        store_cached_climate(*loc, {"gdd5_mean": 100.0})
        store_cached_climate(*loc, {"gdd5_mean": 200.0})
        got = get_cached_climate(*loc)
        self.assertEqual(got["gdd5_mean"], 200.0)

    def test_quantization_means_nearby_lookups_hit_same_row(self):
        """Two pins ~500 m apart should resolve to the same cache row."""
        store_cached_climate(50.0000, -100.0000, {"gdd5_mean": 999.0})
        # ~550 m east and ~550 m north
        got = get_cached_climate(50.0049, -99.9951)
        self.assertIsNotNone(got)
        self.assertEqual(got["gdd5_mean"], 999.0)

    def test_store_orchestration_from_get_climate_summary(self):
        """Calling get_climate_summary with use_cache=True writes to the
        cache and a second call hits the cache."""
        from src.climate import get_climate_summary

        rows = [
            {"date": "2023-06-01", "tmin": 10.0, "tmax": 20.0},
            {"date": "2023-06-02", "tmin": 12.0, "tmax": 22.0},
        ]
        call_count = {"n": 0}

        def _fake_fetcher(lat, lng):
            call_count["n"] += 1
            return rows

        # First call: should hit the fetcher, return cached=False.
        s1 = get_climate_summary(
            60.0, -120.0, use_cache=True, _fetcher=_fake_fetcher
        )
        self.assertIsNotNone(s1)
        self.assertFalse(s1["cached"])
        self.assertEqual(call_count["n"], 1)

        # Second call: should serve from cache, fetcher not called.
        s2 = get_climate_summary(
            60.0, -120.0, use_cache=True, _fetcher=_fake_fetcher
        )
        self.assertIsNotNone(s2)
        self.assertTrue(s2["cached"])
        self.assertEqual(call_count["n"], 1)
        self.assertAlmostEqual(s2["gdd5_mean"], s1["gdd5_mean"])


if __name__ == "__main__":
    unittest.main()
