"""
tests/test_community_names.py — a community's name is never cut in the
library list (V3.19, QF-10, R21).

The first review: at 1366 px Placement › Communities cut the names to about
twelve characters, "Boreal Conifer…", "Boreal Peavin…", "Boreal Shade …",
"Boreal Woodl…", because the facts column took 288 of the list's 392 px and
left the names 104. Names and facts now share the row and fold onto a second
line before either is cut (``src/two_line_rows.py``).

The check reads the row as Qt lays it out: the text the delegate draws, split
into its lines, against the cell's own rectangle (``visualRect``), so it does
not repeat the delegate's arithmetic. ``tests/test_app_smoke.py`` runs the same
check in the real window at 1366 × 768
(``test_no_community_name_is_cut_at_a_laptops_width``).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_community_names_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "community_names.db")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False

from tests._cell_fit import LINE, cut_cells  # noqa: E402

#: The library's width in the window at 1366 × 768 (measured, V3.19).
LIST_WIDTH = 408


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestNoNameIsCut(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-names"])
        _plants_mod.init_db()

    def _panel(self, width=LIST_WIDTH):
        """The panel with its list ``width`` px wide, laid out."""
        from src.polyculture_panel import PolyculturePanel
        panel = PolyculturePanel()
        self.addCleanup(panel.close)
        panel.resize(width + 12, 900)
        panel.show()
        self._settle()
        tree = panel.polyculture_tree
        panel.resize(panel.width() + width - tree.width(), 900)
        self._settle()
        self.assertEqual(tree.width(), width)
        return panel

    def _settle(self):
        for _ in range(4):
            self._app.processEvents()

    def test_every_name_fits_at_the_laptop_width(self):
        tree = self._panel().polyculture_tree
        self.assertGreater(tree.topLevelItemCount(), 20)
        self.assertEqual(cut_cells(tree, columns=(0, 1)), [])

    def _narrow(self, width=240):
        """A bare two-column list ``width`` px wide, too narrow for the
        longest name on one line (the panel will not go below about 360)."""
        from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem
        from src.two_line_rows import TwoLineRows
        tree = QTreeWidget()
        self.addCleanup(tree.close)
        tree.setHeaderHidden(True)
        tree.setColumnCount(2)
        TwoLineRows(tree)                      # the tree owns it
        for name in ("Boreal Peavine & Aster Thicket", "Prairie Pothole Margin",
                     "Bur Oak Community"):
            tree.addTopLevelItem(QTreeWidgetItem(
                [name, "8 plants \u00b7 Partial Shade \u00b7 Dry \u00b7 2 hard to find"]))
        tree.resize(width, 300)
        tree.show()
        self._settle()
        return tree

    def test_a_long_name_takes_two_lines_not_an_ellipsis(self):
        from PyQt6.QtWidgets import QStyleOptionViewItem
        tree = self._narrow()
        item = tree.topLevelItem(0)
        option = QStyleOptionViewItem()
        tree.itemDelegate().initStyleOption(option, tree.indexFromItem(item, 0))
        self.assertIn(LINE, option.text)
        self.assertEqual(option.text.replace(LINE, " "), item.text(0))
        self.assertGreater(tree.visualItemRect(item).height(),
                           1.8 * tree.fontMetrics().height())
        # This narrow, the facts give way before a name does.
        self.assertEqual(cut_cells(tree), [])

    def test_a_short_row_stays_one_line(self):
        tree = self._panel().polyculture_tree
        heights = {tree.visualItemRect(tree.topLevelItem(i)).height()
                   for i in range(tree.topLevelItemCount())}
        self.assertLess(min(heights), 1.8 * tree.fontMetrics().height())

    def test_the_item_keeps_its_whole_name(self):
        """What a screen reader, the tooltip and Place read."""
        tree = self._narrow()
        self.assertEqual(tree.topLevelItem(0).text(0),
                         "Boreal Peavine & Aster Thicket")
        panel_tree = self._panel().polyculture_tree
        for i in range(panel_tree.topLevelItemCount()):
            text = panel_tree.topLevelItem(i).text(0)
            self.assertNotIn(LINE, text)
            self.assertNotIn("\n", text)

    def test_variations_and_groups_fit_too(self):
        panel = self._panel()
        panel._show_variations = True
        panel._group_by = "habitat"
        panel._refresh_polyculture_list()
        self._settle()
        self.assertEqual(cut_cells(panel.polyculture_tree, columns=(0, 1)), [])

    def test_the_facts_break_between_parts(self):
        from src.community_page import two_lines

        class _Metrics:                     # 8 px a character
            def horizontalAdvance(self, text):
                return 8 * len(text)

            def elidedText(self, text, _mode, width):
                return text if 8 * len(text) <= width else \
                    text[:width // 8 - 1] + "…"

        facts = "8 plants · Partial Shade · Dry · 2 hard to find"
        self.assertEqual(two_lines(facts, _Metrics(), 200, " · "),
                         "8 plants · Partial Shade\nDry · 2 hard to find")


if __name__ == "__main__":
    unittest.main()
