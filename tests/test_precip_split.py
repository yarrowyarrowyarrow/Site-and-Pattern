"""
tests/test_precip_split.py — rain/snow precipitation split (by timing).

Covers src/precip_split.py:
  1. partition: rain + snow == total (no inflation), fraction clamping.
  2. annual_total / growing_season_total (Apr–Oct).
  3. add_estimated_split: prairie-curve split keys, summer ≈ all rain.
  4. add_measured_split: passes measured arrays through; rejects bad lengths.

All water amounts are liquid-water equivalent (mm) — no snow-depth conversion.
Pure — no Qt, no DB.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import precip_split as ps  # noqa: E402


class TestPartition(unittest.TestCase):
    def test_rain_plus_snow_equals_total(self):
        total = [20.0, 10.0, 30.0, 40.0]
        frac = [1.0, 0.5, 0.0, 0.25]
        out = ps.partition(total, frac)
        for t, r, s in zip(total, out["rain_mm"], out["snow_mm"]):
            self.assertAlmostEqual(r + s, t, places=5)
        self.assertEqual(out["snow_mm"][0], 20.0)   # all snow
        self.assertEqual(out["rain_mm"][2], 30.0)   # all rain

    def test_fraction_clamped(self):
        out = ps.partition([10.0, 10.0], [2.0, -1.0])
        self.assertEqual(out["snow_mm"][0], 10.0)   # clamped to 1.0
        self.assertEqual(out["snow_mm"][1], 0.0)    # clamped to 0.0


class TestTotals(unittest.TestCase):
    def test_annual(self):
        self.assertEqual(ps.annual_total([1.0, 2.0, 3.0]), 6.0)

    def test_growing_season_apr_oct(self):
        monthly = [100, 100, 100, 1, 2, 3, 4, 5, 6, 7, 100, 100]
        # Apr(1)+May(2)+Jun(3)+Jul(4)+Aug(5)+Sep(6)+Oct(7) = 28
        self.assertEqual(ps.growing_season_total(monthly), 28.0)


class TestEstimatedSplit(unittest.TestCase):
    def setUp(self):
        # Edmonton-ish monthly normal totals.
        self.rain = {"monthly_mm": [22.5, 13.8, 16.1, 26.5, 49.3, 87.1,
                                    91.7, 69.0, 43.4, 21.0, 16.8, 14.5],
                     "annual_mm": 471.7}

    def test_adds_split_keys_and_conserves_total(self):
        out = ps.add_estimated_split(self.rain)
        for key in ("monthly_rain_mm", "monthly_snow_mm",
                    "annual_rain_mm", "annual_snow_mm", "growing_season_rain_mm",
                    "snow_split_source"):
            self.assertIn(key, out)
        # No snow-depth conversion is reported (water-equivalent only).
        self.assertNotIn("monthly_snow_cm", out)
        # rain + snow ≈ the monthly total (no inflation introduced)
        for t, r, s in zip(out["monthly_mm"], out["monthly_rain_mm"],
                           out["monthly_snow_mm"]):
            self.assertAlmostEqual(r + s, t, places=1)

    def test_summer_is_rain_winter_is_snow(self):
        out = ps.add_estimated_split(self.rain)
        # July (index 6) is all rain; January (0) is all snow
        self.assertEqual(out["monthly_snow_mm"][6], 0.0)
        self.assertEqual(out["monthly_rain_mm"][0], 0.0)

    def test_growing_rain_less_than_annual_total(self):
        out = ps.add_estimated_split(self.rain)
        self.assertLess(out["growing_season_rain_mm"], out["annual_mm"])

    def test_no_total_returns_unchanged(self):
        self.assertEqual(ps.add_estimated_split({"annual_mm": 5}),
                         {"annual_mm": 5})
        self.assertIsNone(ps.add_estimated_split(None))


class TestMeasuredSplit(unittest.TestCase):
    def test_passes_arrays_through(self):
        rf = {"monthly_mm": [10.0] * 12}
        rain = [7.0] * 12
        snow = [3.0] * 12
        out = ps.add_measured_split(rf, rain, snow, source="X")
        self.assertEqual(out["monthly_rain_mm"], rain)
        self.assertEqual(out["annual_snow_mm"], 36.0)
        self.assertEqual(out["annual_rain_mm"], 84.0)
        self.assertEqual(out["snow_split_source"], "X")

    def test_bad_length_returns_unchanged(self):
        rf = {"monthly_mm": [10.0] * 12}
        out = ps.add_measured_split(rf, [1.0], [1.0])
        self.assertNotIn("monthly_rain_mm", out)


if __name__ == "__main__":
    unittest.main()
