"""
tests/test_sun_scrub.py — the Sun Path tab's time-of-day scrub (V2.37).

User feedback: "Sunlight analysis needs work. It should show an icon of the sun
moving along the arc of the day and mix this with the shade so you can see the
sun casting the shadows across the day. When I click a date (solstice, equinox
etc) it should automatically show that sun arc for that date."

Two defects sat behind that. The time slider was built, shown, and connected to
NOTHING — `_sun_time_slider` appeared nowhere else in src/ or tests/, so it was
a draggable control that did nothing, which is worse than having none. And
changing the date re-entered anchor-placement mode, so comparing two solstices
meant picking a date, pressing a button and re-clicking the map, every time.
"""

import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                    # noqa: BLE001
    _HAVE_QT = False

_MAP_JS = (pathlib.Path(__file__).resolve().parent.parent
           / "html" / "map" / "06-overlays.js")


class TestSunPathJsContract(unittest.TestCase):
    """Qt-free: the JS entry point and the Python builder must agree."""

    def test_builder_emits_the_js_call(self):
        from src import map_js
        self.assertEqual(map_js.set_sun_path_time(725), "setSunPathTime(725);")
        self.assertEqual(map_js.set_sun_path_time(None), "setSunPathTime(-1);")

    def test_the_js_function_exists(self):
        self.assertIn("function setSunPathTime(",
                      _MAP_JS.read_text(encoding="utf-8"))

    def test_the_marker_is_cleared_with_the_path(self):
        """A sun left hanging over a cleared arc is worse than no sun."""
        src = _MAP_JS.read_text(encoding="utf-8")
        clear = src[src.index("function clearSunPath("):]
        clear = clear[:clear.index("\n    }") + 6]
        self.assertIn("_sunNowLayer", clear)

    def test_scrubbing_does_not_round_trip_to_python(self):
        """The point of holding the payload JS-side: dragging must not re-run
        the solar maths or rebuild the layer group."""
        src = _MAP_JS.read_text(encoding="utf-8")
        fn = src[src.index("function setSunPathTime("):]
        fn = fn[:fn.index("\n    }\n") + 6]
        self.assertIn("_sunPathData", fn)
        self.assertNotIn("bridge.", fn)
        self.assertNotIn("drawSunPath(", fn)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestSunScrubPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _panel(self):
        from src.analysis_panel import AnalysisPanel
        return AnalysisPanel()

    def test_the_slider_is_wired_to_something(self):
        """The regression this file exists for: it used to be connected to
        nothing at all."""
        panel = self._panel()
        seen = []
        panel.sun_time_changed.connect(seen.append)
        panel.set_sun_window(5.0, 21.0)
        panel._sun_time_slider.setValue(15 * 60)
        self.assertIn(15 * 60, seen)

    def test_the_slider_is_dead_until_a_path_exists(self):
        """There is no sun to move before an arc has been drawn, and an
        enabled control that cannot do anything is the original bug."""
        panel = self._panel()
        self.assertFalse(panel._sun_time_slider.isEnabled())

    def test_the_range_is_that_dates_real_daylight(self):
        """You cannot drag the sun to 3 a.m. in June, because it is not there."""
        panel = self._panel()
        panel.set_sun_window(4.8, 22.1)          # a June day in Edmonton
        self.assertEqual(panel._sun_time_slider.minimum(), round(4.8 * 60))
        self.assertEqual(panel._sun_time_slider.maximum(), round(22.1 * 60))

    def test_a_short_winter_day_clamps_the_value_into_range(self):
        panel = self._panel()
        panel.set_sun_window(9.3, 16.2)          # December
        v = panel._sun_time_slider.value()
        self.assertGreaterEqual(v, panel._sun_time_slider.minimum())
        self.assertLessEqual(v, panel._sun_time_slider.maximum())

    def test_the_label_reports_the_clock_time(self):
        panel = self._panel()
        panel.set_sun_window(5.0, 21.0)
        panel._sun_time_slider.setValue(18 * 60 + 30)
        self.assertIn("18:30", panel._sun_time_label.text())

    def test_changing_the_date_asks_for_a_redraw_not_another_map_click(self):
        panel = self._panel()
        asked = []
        panel.sun_redraw_requested.connect(asked.append)
        placements = []
        panel.sun_path_requested.connect(placements.append)
        panel._sun_date.setCurrentIndex(1)        # Winter Solstice
        self.assertTrue(asked, "changing the date did not redraw")
        self.assertIn("Winter", asked[-1]["date_label"])
        self.assertEqual(placements, [],
                         "changing the date re-entered anchor placement")

    def test_place_and_redraw_share_one_config_builder(self):
        """Two paths that must never disagree about what is being drawn."""
        panel = self._panel()
        panel._sun_date.setCurrentIndex(2)
        placed = []
        panel.sun_path_requested.connect(placed.append)
        panel._on_show_sun_path()
        self.assertEqual(placed[-1], panel._sun_config())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestAppWiring(unittest.TestCase):
    def test_the_scrub_and_redraw_are_connected(self):
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "src" / "app.py").read_text(encoding="utf-8")
        self.assertIn("sun_time_changed.connect", src)
        self.assertIn("sun_redraw_requested.connect", src)
        self.assertIn("set_sun_window", src)


if __name__ == "__main__":
    unittest.main()
