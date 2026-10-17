"""
tests/test_site_summary.py — Site Info in four plain lines (WD-2, V3.30;
docs/homeowner/09-words.md §3.2, decision W5).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import site_summary  # noqa: E402

EDMONTON = (53.52, -113.50)
RAIN = {"annual_mm": 456.3, "source": "Open-Meteo ERA5-Land",
        "monthly_mm": [20, 15, 16, 25, 45, 80, 90, 70, 40, 20, 15, 14]}
SOIL = {"summary": {"texture_class": "loam", "ph_top": 7.4}, "fallback": False}


class TheFourLines(unittest.TestCase):

    def _lines(self, **kw):
        facts = dict(lat=EDMONTON[0], lng=EDMONTON[1],
                     label="10423 81 Avenue NW, Strathcona, Edmonton, Alberta")
        facts.update(kw)
        return dict(site_summary.lines(facts))

    def test_all_four_with_the_yards_own_figures(self):
        got = self._lines(zone="3b", frost=(132, 264), rain=RAIN, soil=SOIL)
        self.assertEqual(list(got), ["Where", "Cold", "Rain", "Soil"])
        self.assertEqual(got["Where"],
                         "10423 81 Avenue NW, Strathcona, in the Edmonton "
                         "region.")
        self.assertEqual(got["Cold"],
                         "Plants hardy to zone 3b grow here. Frost-free from "
                         "about May 12 to September 21.")
        self.assertEqual(got["Rain"],
                         "About 460 mm a year, most of it in June and July.")
        self.assertEqual(got["Soil"],
                         "Loam, slightly alkaline (pH 7.4), as mapped near "
                         "your yard.")

    def test_a_fallback_says_typical_for_the_region(self):
        got = self._lines(soil=dict(SOIL, fallback=True))
        self.assertTrue(got["Cold"].endswith(
            "(typical for the Edmonton region)."))
        self.assertTrue(got["Rain"].endswith(
            "(typical for the Edmonton region)."))
        self.assertTrue(got["Soil"].endswith(
            "typical for the Edmonton region."))
        station = dict(RAIN, source="Environment Canada 1981–2010 normal")
        self.assertIn("typical", self._lines(rain=station)["Rain"])

    def test_no_line_for_what_the_app_does_not_have(self):
        far = dict(site_summary.lines(
            {"lat": 43.65, "lng": -79.38, "label": "Toronto"}))
        self.assertEqual(list(far), ["Where"])
        self.assertNotIn("Soil", self._lines())
        self.assertEqual(site_summary.lines({}), [])

    def test_ph_words(self):
        self.assertEqual([site_summary.ph_words(p) for p in
                          (5.0, 6.0, 7.0, 7.5, 8.2)],
                         ["acidic", "slightly acidic", "neutral",
                          "slightly alkaline", "alkaline"])


class TheSiteInfoPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from PyQt6.QtWidgets import QApplication
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(f"needs PyQt6: {exc}")
        cls.app = QApplication.instance() or QApplication(["site-summary"])
        import src.db.plants as P
        tmp = tempfile.mkdtemp()
        P._DATA_DIR, P._DB_PATH = tmp, os.path.join(tmp, "t.db")
        P.init_db()

    def _panel(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        self.addCleanup(panel.close)
        panel.set_pin(*EDMONTON, "10423 81 Avenue NW, Strathcona, Edmonton",
                      fetch=False)
        panel._on_hardiness({"zone": "3b", "source": "NRCan"})
        panel._on_rainfall(dict(RAIN, years_used=30))
        panel._on_soil(dict(SOIL, source="SoilGrids"))
        panel.show()
        return panel

    def test_four_lines_and_details_folded(self):
        panel = self._panel()
        text = panel.summary_text().splitlines()
        self.assertEqual([t.split(":")[0] for t in text],
                         ["Where", "Cold", "Rain", "Soil"])
        self.assertFalse(panel._details.isVisible())
        self.assertFalse(panel._summary_empty.isVisible())
        self.assertFalse(panel._lbl_coverage.isVisible(),
                         "inside the region the Where line says it")
        panel._details_btn.click()
        self.assertTrue(panel._details.isVisible())
        self.assertEqual(panel._details_btn.text(), "Details ▾")

    def test_the_advanced_tools_open_the_details(self):
        panel = self._panel()
        panel.set_advanced_tools(True)
        self.assertTrue(panel._details.isVisible())
        panel.set_advanced_tools(False)
        self.assertFalse(panel._details.isVisible())

    def test_no_pin_says_what_to_do(self):
        from src.site_panel import SitePanel, SUMMARY_EMPTY
        panel = SitePanel()
        self.addCleanup(panel.close)
        panel.show()
        self.assertTrue(panel._summary_empty.isVisible())
        self.assertEqual(panel._summary_empty.text(), SUMMARY_EMPTY)
        self.assertEqual(panel.summary_text(), "")

    def test_the_four_lines_fit_the_side_panel(self):
        """At 1366 x 768 the side panel gives Site Info about 400 px; the
        lines wrap rather than push the page sideways (R8)."""
        panel = self._panel()
        self.assertLessEqual(panel._summary_box.minimumSizeHint().width(),
                             380)

    def test_the_words_of_the_pin_box(self):
        panel = self._panel()
        self.assertEqual(panel._btn_drop.text(), "Click my yard on the map")
        self.assertEqual(panel._btn_search.toolTip(),
                         "Find this address on the map.")


if __name__ == "__main__":
    unittest.main()
