"""
tests/test_map_settings.py — the scroll-wheel zoom step in View › Map
Settings… (V3.07).

It sat at the end of the View row, off-screen at 1366 px, and was never
remembered. The owner moved it to Map Settings on the V3.05 surface audit; it is
saved now and sent to the map each time its page loads. Run against a stand-in
settings store so a test never writes the real profile's.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtWidgets import QApplication, QComboBox, QToolBar
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


class _Settings:
    store: dict = {}

    def value(self, key, default=None):
        return self.store.get(key, default)

    def setValue(self, key, value):
        self.store[key] = value


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheZoomStep(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])

    def setUp(self):
        from src import map_settings_flow as flow
        _Settings.store = {}
        patcher = mock.patch.object(flow, "QSettings", _Settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.flow = flow

        class _Bridge(QObject):
            map_ready = pyqtSignal()

        sent = self.sent = []

        class _Map:
            is_ready = False
            bridge = _Bridge()

            def set_zoom_sensitivity(self, level):
                sent.append(level)

        class _Main:
            map_widget = _Map()

        self.main = _Main()

    def test_fine_until_changed_and_sent_when_the_page_loads(self):
        self.flow.install(self.main)
        self.assertEqual(self.sent, [])                   # not up yet
        self.main.map_widget.bridge.map_ready.emit()
        self.assertEqual(self.sent, ["fine"])

    def test_a_change_is_remembered_and_sent(self):
        self.main.map_widget.is_ready = True
        self.flow.set_zoom_level(self.main, "coarse")
        self.assertEqual(_Settings.store[self.flow.KEY_ZOOM], "coarse")
        self.assertEqual(self.sent, ["coarse"])
        self.assertEqual(self.flow.zoom_level(), "coarse")

    def test_an_unknown_level_reads_as_fine(self):
        _Settings.store = {self.flow.KEY_ZOOM: "ludicrous"}
        self.assertEqual(self.flow.zoom_level(), "fine")

    def test_the_dialog_offers_every_level_and_returns_the_choice(self):
        from src.preferences_dialog import MapPreferencesDialog
        dlg = MapPreferencesDialog(current_token="", zoom_level="fast")
        self.addCleanup(dlg.deleteLater)
        self.assertEqual(dlg.zoom_level(), "fast")
        combo = dlg._zoom
        self.assertEqual([combo.itemData(i) for i in range(combo.count())],
                         [level for level, _w in self.flow.ZOOM_LEVELS])
        combo.setCurrentIndex(combo.findData("normal"))
        self.assertEqual(dlg.zoom_level(), "normal")

    def test_the_view_row_no_longer_holds_it(self):
        from src.toolbar import MainToolbar
        bar = MainToolbar()
        self.addCleanup(bar.deleteLater)
        names = [c.accessibleName()
                 for t in (bar, bar.layers_bar) for c in t.findChildren(QComboBox)]
        self.assertNotIn("Zoom sensitivity", names)
        self.assertFalse(hasattr(bar, "zoom_step_changed"))


if __name__ == "__main__":
    unittest.main()
