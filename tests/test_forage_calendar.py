"""
tests/test_forage_calendar.py

Covers ``src.forage_calendar`` (V2.13) — the whole-design bloom succession +
pollinator forage-gap analysis behind the Analysis → Forage tab:

  * per-month bloom counts, growing-season gap detection, coverage fraction
  * wind-pollinated / flowerless plants don't count as forage (P9 honesty)
  * a flowering plant with no recorded window falls back to a summer relay
  * succession is ordered earliest-first; peak month is the busiest
  * gap-filling suggestions return unplaced natives that flower in a gap
  * the calendar agrees with the score's bloom-continuity sub-score
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.forage_calendar import (build_forage_calendar,   # noqa: E402
                                 gap_filling_suggestions)
from src.habitat_score import GROWING_SEASON_MONTHS  # noqa: E402


def _p(name, bloom="", color="#e0a0d0", form="daisy", **extra):
    d = {"common_name": name, "bloom_period": bloom,
         "flower_color": color, "flower_form": form}
    d.update(extra)
    return d


class TestForageCalendar(unittest.TestCase):

    def test_empty(self):
        cal = build_forage_calendar([])
        self.assertEqual(cal["flowering_plants"], 0)
        self.assertEqual(cal["coverage"], 0.0)
        self.assertIn("No flowering plants", cal["note"])
        self.assertEqual(len(cal["months"]), 12)

    def test_counts_and_gaps(self):
        design = [
            _p("Wild Bergamot", "Jul-Aug"),
            _p("Canada Goldenrod", "Aug-Sep"),
            _p("Smooth Aster", "Aug-Sep"),
            _p("Blanketflower", "Jun-Sep"),
        ]
        cal = build_forage_calendar(design)
        counts = {m["month"]: m["count"] for m in cal["months"]}
        self.assertEqual(counts[8], 4)          # Aug: all four
        self.assertEqual(counts[6], 1)          # Jun: blanketflower only
        self.assertEqual(counts[1], 0)          # Jan: none
        # Growing-season gaps: Apr, May, Oct have no forage.
        self.assertEqual(cal["gap_months"], [4, 5, 10])
        self.assertEqual(cal["covered_growing"], 4)
        self.assertEqual(cal["peak_month"], 8)

    def test_wind_pollinated_excluded(self):
        # A grass with no bloom period and flower_form 'none' is not forage.
        cal = build_forage_calendar([
            _p("Prairie Dropseed", "", form="none", plant_type="grass")])
        self.assertEqual(cal["flowering_plants"], 0)

    def test_flowering_no_window_falls_back_to_summer(self):
        cal = build_forage_calendar([_p("Mystery Bloom", "", form="whorl")])
        self.assertEqual(cal["flowering_plants"], 1)
        counts = {m["month"]: m["count"] for m in cal["months"]}
        self.assertEqual(counts[7], 1)          # summer relay Jun-Sep
        self.assertEqual(counts[4], 0)

    def test_succession_order_and_flags(self):
        cal = build_forage_calendar([
            _p("Late Aster", "Sep-Oct"),
            _p("Early Crocus", "Apr-May"),
            _p("Mid Bergamot", "Jul-Aug"),
        ])
        self.assertEqual([s["name"] for s in cal["succession"]],
                         ["Early Crocus", "Mid Bergamot", "Late Aster"])
        first = cal["succession"][0]
        self.assertTrue(first["months"][3] and first["months"][4])   # Apr, May
        self.assertFalse(first["months"][8])

    def test_continuous_bloom_has_no_gaps(self):
        design = [
            _p("Crocus", "Apr-May"), _p("Golden Bean", "May-Jun"),
            _p("Bergamot", "Jun-Aug"), _p("Goldenrod", "Aug-Oct"),
        ]
        cal = build_forage_calendar(design)
        self.assertEqual(cal["gap_months"], [])
        self.assertEqual(cal["covered_growing"], cal["growing_total"])
        self.assertIn("every growing-season month", cal["note"])

    def test_gap_suggestions(self):
        design = [_p("Bergamot", "Jul-Aug"), _p("Goldenrod", "Aug-Sep")]
        cands = [
            _p("Prairie Crocus", "Apr-May"),
            _p("Golden Bean", "May-Jun"),
            _p("Bergamot", "Jul-Aug"),          # already placed → skipped
            _p("Late Sunflower", "Sep-Oct"),    # Oct is a gap
        ]
        sugg = gap_filling_suggestions(design, cands)
        names = [s["common_name"] for s in sugg]
        self.assertIn("Prairie Crocus", names)
        self.assertNotIn("Bergamot", names)          # already placed
        # Best-fit first: the leader covers the most gap months (Crocus and
        # Golden Bean both fill 2; the single-month sunflower ranks below them).
        self.assertEqual(len(sugg[0]["fills"]), 2)
        fill_counts = [len(s["fills"]) for s in sugg]
        self.assertEqual(fill_counts, sorted(fill_counts, reverse=True))
        gaps = set(build_forage_calendar(design)["gap_months"])
        self.assertTrue(all(set(s["fills"]) <= gaps for s in sugg))
        # The single-gap sunflower sorts after the two-gap fillers.
        self.assertLess(names.index("Golden Bean"), names.index("Late Sunflower"))

    def test_no_suggestions_when_no_gaps(self):
        design = [_p("Crocus", "Apr-May"), _p("Bergamot", "Jun-Aug"),
                  _p("Goldenrod", "Aug-Oct")]
        self.assertEqual(gap_filling_suggestions(design, [_p("X", "Jul-Jul")]), [])

    def test_agrees_with_score_bloom_months(self):
        # The calendar's covered growing months == the score's bloom_months set.
        from src.habitat_score import parse_month_range
        design = [_p("A", "May-Jun"), _p("B", "Aug-Sep")]
        cal = build_forage_calendar(design)
        covered = {m["month"] for m in cal["months"]
                   if m["count"] > 0 and m["is_growing"]}
        score_like = set()
        for p in design:
            for m in parse_month_range(p["bloom_period"]):
                if m in GROWING_SEASON_MONTHS:
                    score_like.add(m)
        self.assertEqual(covered, score_like)


if __name__ == "__main__":
    unittest.main()
