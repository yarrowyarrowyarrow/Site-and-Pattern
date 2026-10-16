"""
tests/test_region_climate.py — climate and coverage from the region pack
(V3.25, ED-6 to ED-8; docs/homeowner/08-edmonton-edition.md §4.5).

Accepted when a Toronto pin gets the outside-the-area sentence and no borrowed
climate, and the frost dates agree everywhere.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import region, region_climate  # noqa: E402

TORONTO = {"latitude": 43.65, "longitude": -79.38}
RED_DEER = {"latitude": 52.27, "longitude": -113.81}
DOWNTOWN = {"latitude": 53.52, "longitude": -113.52}

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


class TheClimateIsThePacks(unittest.TestCase):

    def test_rainfall_by_where_the_pin_is(self):
        pack = region.default()
        months, label = region_climate.rainfall(DOWNTOWN)
        self.assertEqual(months, tuple(pack.climate["monthly_precip_mm"]))
        self.assertIn(pack.climate["station"], label)
        self.assertEqual(region_climate.rainfall(RED_DEER)[0], months,
                         "in the province: the nearest pack's dates (§4.5)")
        self.assertEqual(region_climate.rainfall(TORONTO)[0], ())

    def test_one_frost_pair_everywhere(self):
        """The sun path, Site Info's fallback and the plan's default planting
        window all name the pack's dates (they were May 7, May 15, May 20)."""
        from src.planting_plan import planting_window
        from src.solar import KEY_DATES
        f = region_climate.frost_dates()
        last = region_climate.date_words(f["last"])
        first = region_climate.date_words(f["first"])
        self.assertIn(f"Last Frost (~{last})", KEY_DATES)
        self.assertIn(f"First Frost (~{first})", KEY_DATES)
        self.assertEqual((KEY_DATES[f"Last Frost (~{last})"].month,
                          KEY_DATES[f"Last Frost (~{last})"].day), f["last"])
        self.assertIn(last, planting_window({"plant_type": "wildflower",
                                             "common_name": "no such plant"}))
        self.assertIsNone(region_climate.frost_dates(TORONTO))


class FallbacksStopAt150Km(unittest.TestCase):
    """R32: an offline Toronto pin got Regina's rain, soil and wind."""

    def test_toronto_gets_none(self):
        from src import property_data, wind_flow
        self.assertIsNone(property_data._prairie_soil_fallback(43.65, -79.38))
        self.assertIsNone(wind_flow._fallback_rose(43.65, -79.38))
        # The suite is offline, so the live step fails too.
        self.assertIsNone(property_data.fetch_rainfall(43.65, -79.38))

    def test_edmonton_keeps_its_own(self):
        from src import property_data, wind_flow
        self.assertIsNotNone(property_data._prairie_soil_fallback(53.52, -113.5))
        self.assertIsNotNone(wind_flow._fallback_rose(53.52, -113.5))
        self.assertIsNotNone(property_data.fetch_rainfall(53.52, -113.5))


class TheMapOpensOnTheRegion(unittest.TestCase):

    def _main(self, project):
        calls = []

        class _MW:
            def set_view(self, lat, lng, zoom):
                calls.append((lat, lng, zoom))

        class _Main:
            map_widget = _MW()
        main = _Main()
        main._project = project
        return main, calls

    def test_an_empty_design_opens_on_the_pack(self):
        from src import map_settings_flow
        main, calls = self._main({"features": [], "properties": {}})
        self.assertTrue(map_settings_flow.open_on_region(main))
        view = region.default().map
        self.assertEqual(calls, [(*view["centre"], view["zoom"])])

    def test_a_design_keeps_its_own_view(self):
        from src import map_settings_flow
        main, calls = self._main({"features": [{"type": "Feature"}],
                                  "properties": {}})
        self.assertFalse(map_settings_flow.open_on_region(main))
        main, calls = self._main({"features": [], "properties": {
            "site_config": {"latitude": 50.0, "longitude": -110.0}}})
        self.assertFalse(map_settings_flow.open_on_region(main))
        self.assertEqual(calls, [])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class WhatTheScreensSay(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-region-climate"])

    def test_plan_my_yard_outside_the_provinces(self):
        """Decision E3: disabled, with the reason."""
        from PyQt6.QtWidgets import QDialogButtonBox, QLabel
        from src.generate_design_dialog import GenerateDesignDialog
        cov = region.coverage(TORONTO["latitude"], TORONTO["longitude"])
        dlg = GenerateDesignDialog(has_boundary=True, has_pin=True,
                                   coverage=region.message(cov), outside=True,
                                   coverage_warns=True)
        self.addCleanup(dlg.close)
        ok = dlg.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Ok)
        self.assertFalse(ok.isEnabled())
        self.assertEqual(ok.toolTip(),
                         "Plan My Yard needs a pin in Alberta or Saskatchewan.")
        line = dlg.findChild(QLabel, "plan_coverage")
        self.assertTrue(line.text().startswith("This pin is outside Alberta"))

    def test_plan_my_yard_in_the_region(self):
        from PyQt6.QtWidgets import QDialogButtonBox, QLabel
        from src.generate_design_dialog import GenerateDesignDialog
        cov = region.coverage(DOWNTOWN["latitude"], DOWNTOWN["longitude"])
        dlg = GenerateDesignDialog(has_boundary=True, has_pin=True,
                                   coverage=region.message(cov))
        self.addCleanup(dlg.close)
        ok = dlg.findChild(QDialogButtonBox).button(
            QDialogButtonBox.StandardButton.Ok)
        self.assertTrue(ok.isEnabled())
        self.assertEqual(dlg.findChild(QLabel, "plan_coverage").text(),
                         f"{region.default().name}.")

    def test_site_info_names_the_coverage_and_never_says_ready_outside(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        self.addCleanup(panel.close)
        panel.set_pin(TORONTO["latitude"], TORONTO["longitude"], fetch=False)
        self.assertTrue(panel._lbl_coverage.text().startswith(
            "This pin is outside Alberta and Saskatchewan."))
        panel._set_status("Site data ready.")
        self.assertNotIn("ready", panel._lbl_status.text().lower())
        from src.site_panel import _DASH
        self.assertEqual(panel._pack_frost(), _DASH)
        panel.set_pin(DOWNTOWN["latitude"], DOWNTOWN["longitude"], fetch=False)
        self.assertEqual(panel._lbl_coverage.text(), f"{region.default().name}.")
        panel._set_status("Site data ready.")
        self.assertEqual(panel._lbl_status.text(), "Site data ready.")
        self.assertIn("May 15", panel._pack_frost())

    def test_the_search_box_and_contours_come_from_the_pack(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        self.addCleanup(panel.close)
        pack = region.default()
        self.assertEqual(panel._addr_input.placeholderText(),
                         pack.address_search["placeholder"])
        self.assertEqual(panel._terrain_dl_btn.text(),
                         f"⬇ Download {pack.short} Data")


if __name__ == "__main__":
    unittest.main()
