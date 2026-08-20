"""
tests/test_pull_a_plant.py

The pull-a-plant selector must track the design (F46, fixed V2.42).

The bug a user reported: the list "does not relate to the plants actually on the
design but rather seems like a somewhat arbitrary list". It was arbitrary in a
specific way — `_populate_pull_combo` ran only from `_calc_habitat_score`, which
is wired to a button. So the list was a snapshot of whatever was planted the
last time somebody pressed *Calculate*: it kept species that had since been
removed and never gained the ones added after.

Nothing about the underlying `src/plant_impact.py` was wrong — it takes the
placed plants and always did. The failure was entirely in when the widget was
refreshed, which is exactly the kind of thing a green unit-test suite does not
notice.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                   # pragma: no cover
    _HAVE_QT = False


def _plant(pid, name):
    return {"plant_id": pid, "common_name": name, "lat": 51.05, "lng": -114.07}


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestPullComboFollowsTheDesign(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _panel(self):
        from src.analysis_panel import AnalysisPanel
        return AnalysisPanel()

    def _names(self, panel):
        combo = panel._pull_combo
        return [combo.itemText(i) for i in range(combo.count())
                if combo.itemData(i) is not None]

    def test_placing_plants_populates_the_list_without_pressing_calculate(self):
        """The regression. Before V2.42 this list stayed empty until the user
        found and pressed the habitat-score button."""
        panel = self._panel()
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(2, "Goldenrod")])
        self.assertEqual(self._names(panel), ["Goldenrod", "Milkweed"])

    def test_removing_a_plant_removes_it_from_the_list(self):
        panel = self._panel()
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(2, "Goldenrod")])
        panel.set_placed_plants([_plant(2, "Goldenrod")])
        self.assertEqual(self._names(panel), ["Goldenrod"])

    def test_adding_a_plant_adds_it_to_the_list(self):
        panel = self._panel()
        panel.set_placed_plants([_plant(1, "Milkweed")])
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(3, "Aspen")])
        self.assertEqual(self._names(panel), ["Aspen", "Milkweed"])

    def test_duplicates_of_one_species_appear_once(self):
        panel = self._panel()
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(1, "Milkweed"),
                                 _plant(1, "Milkweed")])
        self.assertEqual(self._names(panel), ["Milkweed"])

    def test_an_empty_design_says_so_and_disables_the_control(self):
        panel = self._panel()
        panel.set_placed_plants([])
        self.assertFalse(panel._pull_combo.isEnabled())
        self.assertEqual(panel._pull_combo.itemText(0), "Place plants first")

    def test_the_users_selection_survives_an_unrelated_edit(self):
        """Rebuilding the combo on every placed plant would silently reset a
        choice the user had already made — trading one annoyance for another."""
        panel = self._panel()
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(2, "Goldenrod")])
        combo = panel._pull_combo
        combo.setCurrentIndex(combo.findData(1))
        self.assertEqual(combo.currentData(), 1)
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(2, "Goldenrod"),
                                 _plant(3, "Aspen")])
        self.assertEqual(combo.currentData(), 1,
                         "adding an unrelated plant reset the selection")

    def test_selection_is_dropped_when_that_species_leaves_the_design(self):
        panel = self._panel()
        panel.set_placed_plants([_plant(1, "Milkweed"), _plant(2, "Goldenrod")])
        combo = panel._pull_combo
        combo.setCurrentIndex(combo.findData(1))
        panel.set_placed_plants([_plant(2, "Goldenrod")])
        self.assertIsNone(combo.currentData())
        self.assertFalse(panel._pull_result.isVisible())

    def test_list_never_offers_a_plant_that_is_not_placed(self):
        """The user-facing invariant, stated directly: every option must be a
        species actually in the design."""
        panel = self._panel()
        placed = [_plant(7, "Wild Bergamot"), _plant(9, "Showy Aster")]
        panel.set_placed_plants(placed)
        offered = {panel._pull_combo.itemData(i)
                   for i in range(panel._pull_combo.count())
                   if panel._pull_combo.itemData(i) is not None}
        self.assertEqual(offered, {7, 9})


if __name__ == "__main__":
    unittest.main()
