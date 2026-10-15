"""
tests/test_water_budget.py — Water: all rows, the pin's rainfall, the weekly
rule (V3.20, OV-7, R4, R38).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_water_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "water.db")

from src import water_budget as wb  # noqa: E402

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False

PLANTS = [
    {"plant_type": "wildflower", "water_needs": "low", "native_to_alberta": 1},
    {"plant_type": "wildflower", "water_needs": "medium", "native_to_alberta": 1},
    {"plant_type": "grass", "water_needs": "low", "native_to_alberta": 1},
    {"plant_type": "shrub", "water_needs": "medium", "native_to_alberta": 0},
    {"plant_type": "tree", "water_needs": "medium", "native_to_alberta": 1},
]


class TheBudget(unittest.TestCase):

    def test_every_type_has_a_row_and_the_rows_are_the_total(self):
        rows = wb.demand_by_type(PLANTS)
        self.assertEqual(set(rows), {"wildflower", "grass", "shrub", "tree"})
        self.assertEqual(rows["wildflower"]["count"], 2)
        weekly = wb.first_summer_weekly_litres(PLANTS)
        self.assertAlmostEqual(sum(r["y1"] for r in rows.values())
                               / wb.GROWING_WEEKS, weekly)

    def test_the_rule_is_weekly_and_said_as_an_estimate(self):
        line = wb.weekly_rule(PLANTS)
        self.assertTrue(line.startswith("First summer: about "), line)
        self.assertIn("L a week in any week without a good rain", line)
        self.assertIn("From year 3: only in a drought.", line)
        self.assertNotIn("surplus", line)
        self.assertEqual(wb.weekly_rule([]), "")

    def test_rainfall_is_the_sites_when_fetched(self):
        months, source = wb.rainfall({})
        self.assertEqual(months, wb.EDMONTON_MONTHLY_RAINFALL_MM)
        self.assertEqual(source, "Edmonton normal")
        site = {"rainfall": {"monthly_mm": [20.0] * 12,
                             "source": "ERA5-Land 1991–2020"}}
        months, source = wb.rainfall(site)
        self.assertEqual(months, (20.0,) * 12)
        self.assertIn("ERA5-Land", source)
        self.assertEqual(wb.rainfall({"rainfall": {"monthly_mm": [1, 2]}})[1],
                         "Edmonton normal")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class ThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-water"])

    def _page(self, site_config=None):
        from src.planning_panel import PlanningPanel
        panel = PlanningPanel()
        self.addCleanup(panel.close)
        panel.set_placed_plants(PLANTS)
        if site_config is not None:
            panel.set_site_config(site_config)
        panel._calc_water()
        return panel._water_results.text()

    def test_wildflowers_and_grasses_have_rows(self):
        text = self._page()
        for row in (">Wildflowers<", ">Grasses<", ">Shrubs<", ">Trees<"):
            self.assertIn(row, text)

    def test_no_surplus_and_the_weekly_rule(self):
        text = self._page()
        self.assertNotIn("surplus", text.lower())
        self.assertNotIn("deficit", text.lower())
        self.assertIn(wb.weekly_rule(PLANTS), text)

    def test_the_sites_rainfall_changes_the_rain_line(self):
        edmonton = self._page()
        self.assertIn("Edmonton normal", edmonton)
        site = self._page({"rainfall": {"monthly_mm": [10.0] * 12,
                                        "source": "ERA5-Land"}})
        self.assertIn("50 mm May–Sep, this site's normals (ERA5-Land)", site)
        self.assertNotIn("Edmonton normal", site)


if __name__ == "__main__":
    unittest.main()
