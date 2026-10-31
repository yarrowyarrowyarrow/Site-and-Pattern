"""
tests/test_wind_with_the_pin.py — the wind comes with the site pin (V3.07).

The Site panel's fetch has read the site's wind rose with every pin since
V2.13, for one line on Site Info, and the Wind page never saw it: it waited for
its own button and fetched the same rose again. The owner said yes to fetching
wind with the pin's other site data on the V3.05 surface audit.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The panels read the catalogue: a database of the test's own.
_TMP = tempfile.mkdtemp(prefix="sp_wind_pin_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "wind_pin.db")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def _rose(deg=292.5, label="WNW", mean=17.0):
    return {"annual": {"prevailing_deg": deg, "prevailing_label": label,
                       "mean_speed": mean, "calm_pct": 3.0},
            "source": "Open-Meteo ERA5 (2015–2024)"}


class _Recorder:
    """Stands in for the two panels and the window: what each was told."""

    def __init__(self):
        self.calls = []
        self.modified = 0
        self._project = {"properties": {"site_config": {
            "latitude": 53.5, "longitude": -113.5}}}
        outer = self

        class _Panel:
            def __getattr__(self, name):
                return lambda *a: outer.calls.append((name, a))

        self.analysis_panel = _Panel()
        self.site_panel = _Panel()
        self.map_widget = object()

    def _mark_modified(self):
        self.modified += 1

    def told(self, name):
        return [a for n, a in self.calls if n == name]


class TestTheWindFlow(unittest.TestCase):

    def test_the_pins_rose_fills_the_wind_page_and_is_kept(self):
        from src import wind_flow
        main = _Recorder()
        wind_flow.on_site_wind(main, _rose())
        (rose, current), = main.told("set_wind_data")
        self.assertEqual(rose["annual"]["prevailing_label"], "WNW")
        self.assertIsNone(current)            # the reading now is Refresh's
        sc = main._project["properties"]["site_config"]
        self.assertEqual(sc["wind_prevailing_deg"], 292.5)
        self.assertEqual(sc["wind_mean_kmh"], 17.0)
        self.assertEqual(main.modified, 1)
        self.assertTrue(main.told("show_wind"))

    def test_offline_with_nothing_cached_is_the_regional_approximation(self):
        from src import wind_flow
        main = _Recorder()
        wind_flow.on_site_wind(main, None)
        (rose, _current), = main.told("set_wind_data")
        self.assertTrue(rose.get("approximate"))
        self.assertIn("Regional approximation", rose.get("source", ""))

    def test_opening_a_design_shows_the_cached_rose_and_changes_nothing(self):
        from src import wind_flow
        main = _Recorder()
        with mock.patch("src.db.plants.get_cached_wind", return_value=_rose()):
            wind_flow.show_cached(main, 53.5, -113.5)
        (rose, _current), = main.told("set_wind_data")
        self.assertTrue(rose["cached"])
        self.assertEqual(main.modified, 0)
        self.assertNotIn("wind_prevailing_deg",
                         main._project["properties"]["site_config"])

    def test_nothing_cached_shows_nothing(self):
        from src import wind_flow
        main = _Recorder()
        with mock.patch("src.db.plants.get_cached_wind", return_value=None):
            wind_flow.show_cached(main, 53.5, -113.5)
        self.assertEqual(main.calls, [])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheSitePanelPassesItOn(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def test_the_rose_the_pin_read_is_handed_on(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        self.addCleanup(panel.deleteLater)
        got = []
        panel.wind_rose_ready.connect(got.append)
        panel._on_wind(_rose())
        self.assertEqual(len(got), 1)
        self.assertIn("WNW", panel._lbl_info_wind.text())
        # The offline fallback is the region's wind, and says so.
        panel.show_wind(dict(_rose(), approximate=True))
        self.assertIn("a regional estimate", panel._lbl_info_wind.text())

    def test_the_wind_page_says_where_its_rose_comes_from(self):
        from src.analysis_panel import AnalysisPanel
        panel = AnalysisPanel()
        self.addCleanup(panel.deleteLater)
        self.assertIn("site pin", panel._wind_status_lbl.text())
        panel.set_site_location(53.5, -113.5)
        self.assertIn("arrives with the site's data",
                      panel._wind_status_lbl.text())
        panel.set_wind_data(_rose(), None)
        self.assertIn("Prevailing WNW", panel._wind_status_lbl.text())


if __name__ == "__main__":
    unittest.main()
