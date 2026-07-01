"""
tests/test_snow.py — winter snow cover & survival metrics.

Covers src/snow.py:
  1. winter_metrics on a synthetic cold winter → accumulates an insulating pack
     (snow-cover days) and reports it averaged per snow-season.
  2. Freeze-thaw cycles, midwinter thaw days, rain-on-snow detection.
  3. reliability_label thresholds (incl. thaw downgrade).
  4. survival_notes framing (conditional benefit + mulch).
  5. Empty / malformed input → None / [].

Pure — no Qt, no DB.
"""

import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import snow  # noqa: E402


def _day(d: date, tmin, tmax, precip=0.0):
    return {"date": d.isoformat(), "tmin": tmin, "tmax": tmax, "precip": precip}


def _cold_winter(year=2021, snowfall_each_day=3.0):
    """Nov 1 (year) → Mar 31 (year+1): hard-frozen, with daily snowfall so the
    modelled pack builds well past the insulating threshold."""
    rows = []
    d = date(year, 11, 1)
    end = date(year + 1, 3, 31)
    while d <= end:
        rows.append(_day(d, -18.0, -8.0, precip=snowfall_each_day))
        d += timedelta(days=1)
    return rows


class TestSnowCover(unittest.TestCase):
    def test_cold_snowy_winter_has_many_cover_days(self):
        m = snow.winter_metrics(_cold_winter())
        self.assertIsNotNone(m)
        self.assertEqual(m["years_used"], 1)
        # Pack crosses the insulating threshold within a few snowy days and holds
        # all winter → most of the ~151 days count.
        self.assertGreater(m["snow_cover_days"], 120)
        self.assertEqual(m["reliability"], "reliable")

    def test_no_snow_no_cover(self):
        # Warm + dry "winter": never accumulates a pack.
        rows = []
        d = date(2021, 11, 1)
        while d <= date(2022, 3, 31):
            rows.append(_day(d, 2.0, 8.0, precip=0.0))
            d += timedelta(days=1)
        m = snow.winter_metrics(rows)
        self.assertEqual(m["snow_cover_days"], 0.0)
        self.assertEqual(m["reliability"], "unreliable")

    def test_pack_resets_between_seasons(self):
        # Two cold winters → averaged, still one-season-like cover count each.
        rows = _cold_winter(2020) + _cold_winter(2021)
        m = snow.winter_metrics(rows)
        self.assertEqual(m["years_used"], 2)
        self.assertGreater(m["snow_cover_days"], 120)


class TestStressMetrics(unittest.TestCase):
    def test_freeze_thaw_cycles(self):
        # Days that cross 0 °C in winter months count as freeze-thaw cycles.
        rows = [
            _day(date(2021, 12, 1), -5.0, 3.0),   # crosses 0 → cycle
            _day(date(2021, 12, 2), -5.0, 3.0),   # crosses 0 → cycle
            _day(date(2021, 12, 3), -10.0, -2.0),  # stays frozen → no
        ]
        m = snow.winter_metrics(rows)
        self.assertEqual(m["freeze_thaw_cycles"], 2.0)

    def test_midwinter_thaw_days(self):
        rows = [
            _day(date(2022, 1, 10), -3.0, 5.0),   # Jan above-freezing → thaw
            _day(date(2022, 1, 11), -3.0, 5.0),
            _day(date(2021, 11, 10), -3.0, 5.0),  # Nov is NOT deep-winter
        ]
        m = snow.winter_metrics(rows)
        self.assertEqual(m["midwinter_thaw_days"], 2.0)

    def test_rain_on_snow_detected(self):
        # Build a pack with cold snowy days, then a warm rainy day on top.
        rows = _cold_winter(2021)
        # Replace a mid-January day with a warm heavy-rain day.
        for r in rows:
            if r["date"] == "2022-01-15":
                r["tmin"], r["tmax"], r["precip"] = 1.0, 6.0, 12.0
        m = snow.winter_metrics(rows)
        self.assertGreaterEqual(m["rain_on_snow_days"], 1.0)


class TestReliabilityLabel(unittest.TestCase):
    def test_thresholds(self):
        self.assertEqual(snow.reliability_label(120, 5), "reliable")
        self.assertEqual(snow.reliability_label(60, 5), "variable")
        self.assertEqual(snow.reliability_label(10, 0), "unreliable")

    def test_frequent_thaw_downgrades_reliable(self):
        # Lots of cover but frequent midwinter thaws → not "reliable".
        self.assertEqual(snow.reliability_label(120, 20), "variable")


class TestSurvivalNotes(unittest.TestCase):
    def test_reliable_notes_are_conditional(self):
        notes = snow.survival_notes({"reliability": "reliable",
                                     "midwinter_thaw_days": 0,
                                     "freeze_thaw_cycles": 0})
        text = " ".join(notes).lower()
        self.assertIn("zone milder", text)
        self.assertIn("thin-snow", text)        # design for the bad year

    def test_unreliable_recommends_mulch(self):
        notes = snow.survival_notes({"reliability": "unreliable",
                                     "midwinter_thaw_days": 0,
                                     "freeze_thaw_cycles": 0})
        self.assertIn("mulch", " ".join(notes).lower())

    def test_chinook_note_when_thaws_frequent(self):
        notes = snow.survival_notes({"reliability": "variable",
                                     "midwinter_thaw_days": 20,
                                     "freeze_thaw_cycles": 50})
        text = " ".join(notes).lower()
        self.assertIn("chinook", text)
        self.assertIn("heave", text)

    def test_empty(self):
        self.assertEqual(snow.survival_notes(None), [])


class TestEdgeCases(unittest.TestCase):
    def test_empty_input(self):
        self.assertIsNone(snow.winter_metrics([]))
        self.assertIsNone(snow.winter_metrics(None))

    def test_malformed_rows_skipped(self):
        rows = [{"date": "nope", "tmin": 1, "tmax": 2},
                {"date": "2022-01-01"},  # missing temps
                _day(date(2022, 1, 2), -10, -2)]
        m = snow.winter_metrics(rows)
        self.assertIsNotNone(m)
        self.assertEqual(m["years_used"], 1)


if __name__ == "__main__":
    unittest.main()
