"""
tests/test_fill_tab_widget.py

V1.60 — FillTabWidget spreads its tabs across the full strip width (so there's
no empty gap to the right of the last tab) even with a QTabBar::tab stylesheet
applied, where Qt's own setExpanding is ignored. Qt smoke test; skips when
PyQt6 isn't installed.
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
class TestFillTabWidget(unittest.TestCase):

    _app = None

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])

    def test_tabs_fill_the_bar_width(self):
        from PyQt6.QtWidgets import QWidget
        from src.fill_tab_widget import FillTabWidget, _FillTabBar
        w = FillTabWidget()
        # Document mode lets the bar span the full width (as the app sets it).
        w.setDocumentMode(True)
        w.setStyleSheet("QTabBar::tab { padding: 4px 10px; }")
        for name in ("Site", "Plants", "Structures"):
            w.addTab(QWidget(), name)
        self.assertIsInstance(w.tabBar(), _FillTabBar)
        w.resize(600, 120)
        w.show()
        self._app.processEvents()
        bar = w.tabBar()
        # End-to-end: the tabs span the whole strip — the last tab reaches the
        # widget's right edge (no empty gap), and each tab expanded past its
        # tight content width.
        last = bar.tabRect(bar.count() - 1)
        self.assertGreaterEqual(last.right(), w.width() - 8)
        widths = [bar.tabSizeHint(i).width() for i in range(3)]
        self.assertGreater(min(widths), 30)
        w.hide()
        w.deleteLater()


if __name__ == "__main__":
    unittest.main()
