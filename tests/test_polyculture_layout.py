"""
tests/test_polyculture_layout.py — the Plant Communities column budget (V2.30).

Reported: with communities added to the mix, the library list showed about three
rows out of sixty.

Two causes, and the second is the interesting one.

1. Selecting any community clamped the tree to seven rows
   (``_TREE_COLLAPSED_ROWS``), which is deliberate — the members list and the
   pattern card need the room — but became the binding constraint once (2) was
   fixed.
2. The tree was the ONLY stretch child in the column with no minimum height, and
   the file set no size policy anywhere. Everything below it was rigid or
   growing: the members pane was pinned min == max up to 300 px, the pattern card
   had a 120 px floor, and the mix box grew ~26 px per row with no cap inside a
   stretch-0 collapsible pane — and a QVBoxLayout hands a stretch-0 child its
   whole sizeHint before the stretch children get anything. So every row added
   to the mix came directly out of the community list.

The sibling tab had already solved this and written down why
(``src/plant_panel.py:262-266``, ``:519-521``, ``:948-962``); this panel simply
never picked the recipe up.

Needs Qt, so it self-skips where PyQt6 is absent — the same guard the other
widget tests use.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed")
class PolycultureColumnBudgetTest(unittest.TestCase):
    """The community list must survive a full mix."""

    app = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def _panel(self):
        from src.polyculture_panel import PolyculturePanel
        panel = PolyculturePanel()
        panel.resize(420, 900)                 # a normal sidebar height
        panel.show()
        self.app.processEvents()
        return panel

    def test_the_list_keeps_its_floor_with_a_full_mix(self):
        import src.polyculture_panel as P
        panel = self._panel()
        try:
            # Fill the mix to its cap, the state the user reported.
            panel._mix_communities = [
                {"id": i, "name": f"Community {i}", "weight": 1}
                for i in range(panel._MIX_COMMUNITY_MAX)
            ]
            panel._refresh_community_mix()
            panel._placement_panel.set_expanded(True, persist=False)
            self.app.processEvents()
            panel._refit_placement_pane()
            self.app.processEvents()

            row_h = max(1, panel.polyculture_tree.sizeHintForRow(0) or 19)
            floor = row_h * P._TREE_MIN_ROWS
            self.assertGreaterEqual(
                panel.polyculture_tree.minimumHeight(), floor,
                "the community list has no effective floor, so the placement "
                "pane can squeeze it to nothing again")
        finally:
            panel.close()
            panel.deleteLater()

    def test_the_mix_rows_are_bounded(self):
        """Eight mix rows must not add eight rows of height. They scroll."""
        import src.polyculture_panel as P
        panel = self._panel()
        try:
            panel._mix_communities = [
                {"id": i, "name": f"Community {i}", "weight": 1}
                for i in range(panel._MIX_COMMUNITY_MAX)
            ]
            panel._refresh_community_mix()
            self.app.processEvents()
            cap = panel._mix_community_scroll.maximumHeight()
            self.assertLessEqual(
                cap, P._MIX_ROWS_VISIBLE * 26 + 8,
                "the mix rows are not capped — they grow without bound and the "
                "space comes out of the community list")
            self.assertLess(
                cap, panel._MIX_COMMUNITY_MAX * 26,
                "the cap is loose enough that a full mix still costs a full "
                "list's worth of height")
        finally:
            panel.close()
            panel.deleteLater()

    def test_the_placement_pane_will_not_out_compete_the_list(self):
        """`Minimum` vertical policy is the specific call this panel lacked —
        it tells the layout the pane accepts its sizeHint and no more."""
        from PyQt6.QtWidgets import QSizePolicy
        panel = self._panel()
        try:
            self.assertEqual(
                panel._placement_body.sizePolicy().verticalPolicy(),
                QSizePolicy.Policy.Minimum,
                "the placement body has no Minimum vertical policy, so it "
                "takes its full sizeHint out of the stretch children")
        finally:
            panel.close()
            panel.deleteLater()

    def test_the_members_pane_can_yield(self):
        """It was pinned min == max up to 300 px, i.e. perfectly rigid."""
        panel = self._panel()
        try:
            members = [{"plant_id": i, "common_name": f"Plant {i}",
                        "role": "", "x_offset_m": 0, "y_offset_m": 0}
                       for i in range(10)]
            panel._render_member_rows(members)
            self.app.processEvents()
            self.assertLess(
                panel._members_scroll.minimumHeight(),
                panel._members_scroll.maximumHeight(),
                "the members pane is pinned rigid again — min == max means it "
                "is one more block the community list has to pay for")
        finally:
            panel.close()
            panel.deleteLater()


if __name__ == "__main__":
    unittest.main()
