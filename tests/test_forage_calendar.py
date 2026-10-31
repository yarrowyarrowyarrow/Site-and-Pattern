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

    def test_a_grass_sedge_or_rush_is_never_forage(self):
        # V2.91 (F182): all 78 carry a bloom period, and a bloom period used
        # to count before anything else was looked at. The owner's rule: they
        # flower, but not for bees, whatever the period says.
        for kind, name in (("grass", "Rough Fescue"), ("sedge", "Beaked Sedge"),
                           ("rush", "Wire Rush")):
            with self.subTest(kind):
                cal = build_forage_calendar([
                    _p(name, "June-July", form="plume", plant_type=kind)])
                self.assertEqual(cal["flowering_plants"], 0)
                self.assertEqual(cal["months"][5]["count"], 0)     # June

    def test_grass_bloom_does_not_hide_a_forage_gap(self):
        # A prairie mix: crocus in spring, aster in late summer, and grasses
        # flowering between them. June and July are a gap for a bee.
        design = [
            _p("Prairie Crocus", "Apr-May"),
            _p("Smooth Aster", "Aug-Oct"),
            _p("Rough Fescue", "June-July", form="plume", plant_type="grass"),
            _p("Blue Grama Grass", "July-August", form="plume",
               plant_type="grass"),
            _p("Needle and Thread Grass", "May-Jun", form="plume",
               plant_type="grass"),
        ]
        cal = build_forage_calendar(design)
        self.assertEqual(cal["gap_months"], [6, 7])
        self.assertEqual(cal["flowering_plants"], 2)
        self.assertNotIn("every growing-season month", cal["note"])

    def test_a_grass_is_never_suggested_for_a_gap(self):
        design = [_p("Crocus", "Apr-May"), _p("Goldenrod", "Aug-Oct")]
        cands = [_p("Rough Fescue", "June-July", form="plume",
                    plant_type="grass"),
                 _p("Wild Bergamot", "Jul-Aug")]
        names = [s["common_name"]
                 for s in gap_filling_suggestions(design, cands)]
        self.assertEqual(names, ["Wild Bergamot"])

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


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestFoodMonthByMonth(unittest.TestCase):
    """Design › Food's month by month (Planning › Wildlife until V3.08) is a
    second forage calendar, reading ``bloom_period`` straight from the
    database. It listed every grass under "Pollinator blooms" and let grasses
    close a "nectar gap" (V2.91, F182)."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import tempfile
        import src.db.plants as plants_mod
        import src.permadesign_api as api
        tmp = tempfile.mkdtemp(prefix="permadesign_forage_panel_")
        plants_mod._DATA_DIR = tmp
        plants_mod._DB_PATH = os.path.join(tmp, "permadesign_test.db")
        plants_mod.init_db()
        api._DB_READY = True
        from PyQt6.QtWidgets import QApplication
        cls._app = (QApplication.instance()
                    or QApplication(["test_forage_calendar"]))
        cls.rows = {r["common_name"]: r for r in api.query_plants()}

    def _june_and_july(self, names):
        """Design › Food's month by month (V3.08; Planning › Wildlife until
        then): the pollinators' blooms in June and July, and the gap line."""
        from src.food_page import FoodPage
        from src.what_it_feeds import month_by_month
        ids = [self.rows[n]["id"] for n in names]
        year = month_by_month(ids)
        out = {m: year["months"][m - 1]["pollinators"] for m in (6, 7)}
        page = FoodPage()
        try:
            page.set_placed_plants([{"plant_id": i} for i in ids])
            page.refresh()
            for m in (6, 7):
                blooms = page._tree.topLevelItem(m - 1).child(0)
                self.assertEqual([blooms.child(i).text(1)
                                  for i in range(blooms.childCount())],
                                 out[m] or ["—"])
            return out, page._gap_label.text()
        finally:
            page.close()

    def test_no_grass_is_listed_as_a_pollinator_bloom(self):
        months, gaps = self._june_and_july(
            ["Prairie Crocus", "Smooth Aster", "Rough Fescue",
             "Blue Grama Grass"])
        for m, names in months.items():
            with self.subTest(month=m):
                self.assertNotIn("Rough Fescue", names)
                self.assertNotIn("Blue Grama Grass", names)
        # So June and July show as the gap they are for a bee.
        self.assertIn("Nectar gaps in the growing season: Jun, Jul.", gaps)


if __name__ == "__main__":
    unittest.main()
