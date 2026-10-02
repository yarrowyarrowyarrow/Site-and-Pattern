"""
tests/test_map_furniture.py — the north arrow and the scale bar (F205, V3.06).

The scale's arithmetic is the page's own (html/map/11-map-furniture.js), run
in node as test_fit_when_shown runs 02-boundary.js. The View menu's switches
are src/map_furniture_flow.py, run against a stand-in settings store so a test
never writes the real profile's.
"""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src import map_js  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "html" / "map" / "11-map-furniture.js"

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QMenu
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def _node():
    return shutil.which("node") or shutil.which("nodejs")


def _scales(cases):
    """scaleBarFor over ``cases`` of (metres per pixel, unit), in node."""
    script = "\n".join([
        _SCRIPT.read_text(encoding="utf-8"),
        "var cases = %s;" % json.dumps(cases),
        "console.log(JSON.stringify(cases.map(function (c) {"
        " return scaleBarFor(c[0], SCALE_MAX_PX, c[1]); })));",
    ])
    proc = subprocess.run([_node(), "-"], input=script, capture_output=True,
                          text=True, timeout=60, encoding="utf-8")
    if proc.returncode != 0:
        raise AssertionError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipIf(_node() is None, "no node binary")
class TestTheScale(unittest.TestCase):

    def test_kilometres_unless_asked_for_metres(self):
        km, m = _scales([[1.0, "km"], [1.0, "m"]])
        self.assertEqual((km["label"], km["px"]), ("0.1 km", 100))
        self.assertEqual((m["label"], m["px"]), ("100 m", 100))

    def test_a_yard_and_a_quarter_section(self):
        yard_km, yard_m, farm = _scales([[0.05, "km"], [0.05, "m"],
                                         [40.0, "km"]])
        self.assertEqual(yard_km["label"], "0.005 km")
        self.assertEqual(yard_m["label"], "5 m")
        self.assertEqual((farm["label"], farm["px"]), ("2 km", 50))

    def test_a_round_length_that_fits_in_the_bar(self):
        mpps = [0.013, 0.07, 0.4, 2.5, 9.0, 33.0, 150.0, 777.0]
        for unit in ("km", "m"):
            out = _scales([[mpp, unit] for mpp in mpps])
            for mpp, s in zip(mpps, out):
                self.assertLessEqual(s["px"], 120, (mpp, unit, s))
                self.assertGreaterEqual(s["px"], 24, (mpp, unit, s))
                digits = s["label"].split()[0].replace(".", "").lstrip("0")
                self.assertIn(digits[0], "125", s)        # 1, 2 or 5
                self.assertTrue(set(digits[1:]) <= {"0"}, s)

    def test_nothing_to_measure_draws_nothing(self):
        self.assertEqual(_scales([[0, "km"], [float("nan"), "m"]]),
                         [None, None])


class TestTheBuilders(unittest.TestCase):

    def test_what_the_page_is_told(self):
        self.assertEqual(map_js.set_north_arrow(True), "setNorthArrow(true);")
        self.assertEqual(map_js.set_scale_bar(False, "m"),
                         'setScaleBar(false, "m");')
        self.assertEqual(map_js.set_scale_bar(True, "miles"),
                         'setScaleBar(true, "km");')


class _Settings:
    """A dict-backed QSettings, so tests never touch the real profile."""
    store: dict = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheSwitches(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def setUp(self):
        from src import map_furniture_flow as flow
        _Settings.store = {}
        patcher = mock.patch.object(flow, "QSettings", _Settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.flow = flow

        class _Bridge(QObject):
            scale_unit_changed = pyqtSignal(str)
            map_ready = pyqtSignal()

        calls = self.calls = []

        class _Map:
            is_ready = False
            bridge = _Bridge()

            def set_north_arrow(self, on):
                calls.append(("arrow", on))

            def set_scale_bar(self, on, unit):
                calls.append(("scale", on, unit))

        class _Main:
            map_widget = _Map()

        self.main = _Main()
        self.menu = QMenu()
        self.addCleanup(self.menu.deleteLater)
        flow.install(self.main, self.menu)

    def _labels(self):
        return [a.text().replace("&", "") for a in self.menu.actions()]

    def test_both_on_in_kilometres_until_changed(self):
        self.assertEqual(self._labels(), ["North Arrow", "Scale Bar",
                                          "Scale Units"])
        self.assertTrue(self.main._act_north_arrow.isChecked())
        self.assertTrue(self.main._act_scale_bar.isChecked())
        self.assertTrue(self.main._act_scale_km.isChecked())
        self.assertEqual(self.calls, [])                  # the map is not up
        self.main.map_widget.bridge.map_ready.emit()
        self.assertEqual(self.calls, [("arrow", True), ("scale", True, "km")])

    def test_switching_each_off_is_remembered(self):
        self.main.map_widget.is_ready = True
        self.main._act_north_arrow.setChecked(False)
        self.assertIs(_Settings.store[self.flow.KEY_ARROW], False)
        self.assertIn(("arrow", False), self.calls)
        self.main._act_scale_bar.setChecked(False)
        self.assertEqual(self.calls[-1], ("scale", False, "km"))
        self.assertEqual(self.flow.state(), {"north_arrow": False,
                                             "scale_bar": False, "unit": "km"})

    def test_metres_from_the_menu_or_the_bar(self):
        self.main.map_widget.is_ready = True
        self.main._act_scale_m.trigger()
        self.assertEqual(_Settings.store[self.flow.KEY_UNIT], "m")
        self.assertEqual(self.calls[-1], ("scale", True, "m"))
        # A click on the bar switches back, and the menu follows it.
        self.main.map_widget.bridge.scale_unit_changed.emit("km")
        self.assertTrue(self.main._act_scale_km.isChecked())
        self.assertEqual(self.calls[-1], ("scale", True, "km"))

    def test_a_switch_before_the_map_has_loaded_waits_for_it(self):
        self.main._act_north_arrow.setChecked(False)
        self.assertIs(_Settings.store[self.flow.KEY_ARROW], False)
        self.assertEqual(self.calls, [])                  # not sent yet
        self.main.map_widget.bridge.map_ready.emit()
        self.assertEqual(self.calls, [("arrow", False), ("scale", True, "km")])

    def test_a_setting_saved_as_text_still_reads(self):
        _Settings.store = {self.flow.KEY_ARROW: "false",
                           self.flow.KEY_UNIT: "furlongs"}
        self.assertEqual(self.flow.state(), {"north_arrow": False,
                                             "scale_bar": True, "unit": "km"})


if __name__ == "__main__":
    unittest.main()
