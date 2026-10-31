"""
tests/test_share_panel.py — Share › Export (V3.08).

What leaves the app had four homes (File's exports, Learn › Present, View ›
Growth Snapshots and the 3D preview's own buttons). The Export page is a list
of them that calls what those already do: nothing on it is a second way of
exporting, and the tests hold it to that.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication, QLabel, QWidget
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestExport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-share-panel"])

    def _panel(self):
        from src.share_panel import SharePanel
        main = mock.Mock()
        panel = SharePanel(main)
        self.addCleanup(panel.close)
        return panel, main

    def test_every_export_is_a_button_in_the_order_a_person_needs_it(self):
        from src.share_panel import EXPORTS
        panel, _main = self._panel()
        self.assertEqual(list(panel.buttons),
                         [words for _s, rows in EXPORTS for words, _g, _a in rows])
        self.assertEqual(list(panel.buttons)[0], "Export PDF…")
        for words, btn in panel.buttons.items():
            self.assertTrue(btn.toolTip(), f"{words} says nothing it gives")

    def test_the_documents_call_what_the_file_menu_calls(self):
        panel, main = self._panel()
        for words, method in (("Export PDF…", "_on_export_pdf"),
                              ("Planting plan…", "_on_export_shopping_list"),
                              ("Order file…", "_on_export_order_file")):
            panel.buttons[words].click()
            getattr(main, method).assert_called_once_with()

    def test_the_pictures_open_where_they_are_rendered(self):
        # Stand-ins for the two windows' modules: the 3D preview's imports
        # QtWebEngine, which cannot load once a QApplication exists.
        panel, main = self._panel()
        scene3d, snapshots = mock.Mock(), mock.Mock()
        with mock.patch.dict(sys.modules, {"src.scene3d_window": scene3d,
                                           "src.snapshot_window": snapshots}):
            panel.buttons["Presentation still…"].click()
            panel.buttons["Before / after…"].click()
            panel.buttons["Growth Snapshots…"].click()
        scene3d.open_3d_view.assert_called_with(main)
        view = scene3d.open_3d_view.return_value
        view._on_presentation_still.assert_called_once_with()
        view._on_before_after.assert_called_once_with()
        snapshots.open_snapshot_view.assert_called_once_with(main)

    def test_a_widget_added_goes_last_above_the_stretch(self):
        panel, _main = self._panel()
        box = QLabel("Where to buy")
        panel.add_to_export(box)
        lay = panel._export_layout
        self.assertIs(lay.itemAt(lay.count() - 2).widget(), box)
        self.assertIsNotNone(lay.itemAt(lay.count() - 1).spacerItem())

    def test_present_and_export_are_its_pages_once_arranged(self):
        """Standalone it has Export; Present arrives from the Learn panel
        (src/side_panel_layout.py), which still drives it."""
        panel, _main = self._panel()
        self.assertEqual([panel._tabs.tabText(i)
                          for i in range(panel._tabs.count())], ["Export"])
        present = QWidget()
        panel._tabs.insertTab(0, present, "Present")
        self.assertIs(panel._tabs.widget(1), panel.export_page)


if __name__ == "__main__":
    unittest.main()
