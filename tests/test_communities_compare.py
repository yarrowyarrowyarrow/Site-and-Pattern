"""
tests/test_communities_compare.py — communities as things to compare (F196,
V3.05).

The V2.98 review: sixty-one names with size, species count, sun and moisture
only after a click; "For a creature…" a 721-entry dropdown typing could not
search (the Monarch was entry 446); and the builder's Cancel discarding a
community laid out by hand without asking.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_communities_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheRowSaysWhatItIs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])
        _plants.init_db()

    def test_the_facts_read_plainly(self):
        from src.polyculture_panel import community_facts
        self.assertEqual(community_facts({"member_count": 8, "facets": {
            "sun": "Full Sun", "moisture": "Mesic"}}), "8 plants · Full Sun · Mesic")
        self.assertEqual(community_facts({"member_count": 1, "facets": {
            "sun": "Unknown", "moisture": "Mixed"}}), "1 plant")

    def test_every_community_in_the_library_carries_them(self):
        from src.polyculture_panel import PolyculturePanel
        panel = PolyculturePanel()
        tree = panel.polyculture_tree
        self.assertEqual(tree.columnCount(), 2)
        rows = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
        rows = [r for r in rows if r.data(0, 0x0100) is not None]   # UserRole
        self.assertGreater(len(rows), 20)
        for r in rows:
            self.assertRegex(r.text(1), r"^\d+ plants?")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestFindACreature(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])
        _plants.init_db()

    def test_typing_narrows_the_list(self):
        from src.polyculture_panel import _CreaturePickerDialog
        dlg = _CreaturePickerDialog()
        everyone = dlg.visible_names()
        self.assertGreater(len(everyone), 50)
        dlg._find.setText("monarch")
        shown = dlg.visible_names()
        self.assertTrue(shown and all("monarch" in n.lower() for n in shown),
                        shown)
        self.assertIn("monarch", dlg._combo.currentText().lower())
        self.assertEqual(dlg.selected()["name"].lower().count("monarch"), 1)
        dlg._find.setText("")
        self.assertEqual(dlg.visible_names(), everyone)


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestCancelAsksFirst(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-tests"])
        _plants.init_db()

    def _dialog(self):
        from src.polyculture_panel import PolycultureBuilderDialog
        dlg = PolycultureBuilderDialog(None)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def _answer(self, label):
        """Stand in for the person: the question's ``exec`` clicks ``label``."""
        def exec_(box):
            for b in box.buttons():
                if b.text() == label:
                    b.click()
            return 0
        return mock.patch.object(QMessageBox, "exec", exec_)

    def test_nothing_built_closes_without_asking(self):
        dlg = self._dialog()
        with mock.patch.object(QMessageBox, "exec") as asked, \
                mock.patch.object(QDialog, "reject") as closed:
            dlg.reject()
        asked.assert_not_called()
        closed.assert_called_once()

    def test_a_laid_out_community_is_kept_unless_discarded(self):
        dlg = self._dialog()
        dlg.name_input.setText("Back fence pollinators")
        with self._answer("Keep editing"), \
                mock.patch.object(QDialog, "reject") as closed:
            dlg.reject()
        closed.assert_not_called()
        with self._answer("Discard"), \
                mock.patch.object(QDialog, "reject") as closed:
            dlg.reject()
        closed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
