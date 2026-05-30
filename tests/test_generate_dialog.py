"""
tests/test_generate_dialog.py

Headless-Qt smoke test for src/generate_design_dialog.py:GenerateDesignDialog,
focused on the V1.47 "design for wildlife" fauna picker. The dialog takes its
fauna_options as a plain list of dicts (it never touches the DB), so these
tests need no temp DB.

Same skip-gracefully pattern as tests/test_plant_panel_smoke.py — skips cleanly
when PyQt6 is unavailable. Run locally with::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_generate_dialog -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force offscreen platform BEFORE importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


_FAUNA_OPTS = [
    {"id": 8, "common_name": "Monarch", "taxon": "lepidoptera", "icon": "🦋"},
    {"id": 12, "common_name": "Bumblebees", "taxon": "bee", "icon": "🐝"},
]


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestGenerateDialogFaunaPicker(unittest.TestCase):

    _app = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication([])

    def _make(self, **kw):
        from src.generate_design_dialog import GenerateDesignDialog
        kw.setdefault("has_boundary", False)
        kw.setdefault("has_pin", True)
        return GenerateDesignDialog(**kw)

    def test_no_picker_without_options(self):
        dlg = self._make()
        self.assertIsNone(dlg._fauna_list)
        self.assertEqual(dlg.selected_fauna(), [])
        dlg.deleteLater()

    def test_picker_lists_options(self):
        dlg = self._make(fauna_options=_FAUNA_OPTS)
        self.assertIsNotNone(dlg._fauna_list)
        self.assertEqual(dlg._fauna_list.count(), 2)
        self.assertEqual(dlg.selected_fauna(), [])      # nothing ticked yet
        dlg.deleteLater()

    def test_selection_returns_ids_not_rows(self):
        from PyQt6.QtCore import Qt
        dlg = self._make(fauna_options=_FAUNA_OPTS)
        dlg._fauna_list.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(dlg.selected_fauna(), [8])     # the id, not the row
        dlg._fauna_list.item(1).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(sorted(dlg.selected_fauna()), [8, 12])
        dlg.deleteLater()

    def test_option_without_id_is_skipped(self):
        dlg = self._make(fauna_options=[{"common_name": "Nameless"}] + _FAUNA_OPTS)
        self.assertEqual(dlg._fauna_list.count(), 2)    # the id-less one dropped
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
