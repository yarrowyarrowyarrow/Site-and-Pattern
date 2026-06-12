"""
tests/test_plant_list_legend.py

V1.64 — the expanded-row calendar legend wraps onto extra lines when its
labels don't fit horizontally (macOS's wider font pushes "Pruning" onto a
second line), and the heights reserved by sizeHint/paint must track the
wrap count or the legend paints straight over the notes text below.
Qt smoke test; skips when PyQt6 isn't installed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestLegendRowCount(unittest.TestCase):

    _app = None

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _delegate(self):
        from src.plant_list_view import PlantRowDelegate
        return PlantRowDelegate()

    def test_single_row_when_wide(self):
        # With effectively unlimited width every legend entry fits one line.
        self.assertEqual(self._delegate()._legend_rows_for_width(10000), 1)

    def test_wraps_when_narrow(self):
        # At 120 px the six legend entries cannot fit on one line on any
        # platform's font — the count must report the wrap.
        self.assertGreaterEqual(self._delegate()._legend_rows_for_width(120), 2)

    def test_rows_never_decrease_as_panel_narrows(self):
        d = self._delegate()
        rows = [d._legend_rows_for_width(w) for w in (120, 180, 244, 400, 10000)]
        self.assertEqual(rows, sorted(rows, reverse=True))


if __name__ == "__main__":
    unittest.main()
