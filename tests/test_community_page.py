"""
tests/test_community_page.py — a community's page beside the list (F206, V3.09).

The owner wanted communities shown as plants are: in the frame beside the list,
with small photographs of the members, the description, and each member's page
a click away. The page is ``src/community_page.py``; the frame is
``src/species_flyout.py``; the list opens it (``polyculture_panel``).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_community_page_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "community_page.db")

try:
    from PyQt6.QtWidgets import QApplication, QToolButton, QWidget
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestCommunityPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-community"])
        _plants_mod.init_db()
        from src.db import polycultures
        rows = polycultures.get_all_polycultures(top_level_only=True)
        cls.community = next(polycultures.get_polyculture_by_id(r["id"])
                             for r in rows if r.get("id") is not None)

    def _species(self):
        return {int(m["plant_id"]) for m in self.community["members"]}

    def test_it_shows_the_name_the_facts_the_plants_and_the_description(self):
        from src.community_page import CommunityPage
        page = CommunityPage()
        self.addCleanup(page.close)
        page.show_community(self.community)
        self.assertEqual(page._name.text(), self.community["name"])
        self.assertRegex(page._facts.text(), r"^\d+ plants?")
        self.assertEqual(set(page._tiles), self._species())
        self.assertTrue(page._about.text())
        for pid, tile in page._tiles.items():
            # A photograph or, until one is cached, the type's colour: never
            # an empty box.
            self.assertFalse(tile.icon().isNull(), pid)
            self.assertTrue(tile.accessibleName())

    def test_a_member_opens_its_page_and_esc_closes(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from src.community_page import CommunityPage
        page = CommunityPage()
        self.addCleanup(page.close)
        page.show_community(self.community)
        asked, closed = [], []
        page.member_requested.connect(asked.append)
        page.close_requested.connect(lambda: closed.append(True))
        pid, tile = next(iter(page._tiles.items()))
        tile.click()
        self.assertEqual(asked, [{"id": pid}])
        QTest.keyClick(page, Qt.Key.Key_Escape)
        self.assertEqual(closed, [True])

    def test_place_names_this_community(self):
        from src.community_page import CommunityPage
        page = CommunityPage()
        self.addCleanup(page.close)
        page.show_community(self.community)
        placed = []
        page.place_requested.connect(placed.append)
        page._place.click()
        self.assertEqual(placed, [self.community["id"]])

    def test_the_frame_drops_into_a_plant_and_back(self):
        from src.community_flyout import CommunityFlyout as SpeciesFlyout
        holder = QWidget()
        self.addCleanup(holder.close)
        anchor = QWidget(holder)
        holder.resize(1000, 700)
        anchor.resize(1000, 700)
        holder.show()
        fly = SpeciesFlyout(holder, anchor)
        fly.show_community(self.community)
        self.assertTrue(fly.community.isVisible())
        self.assertFalse(fly.page.isVisible())
        self.assertTrue(fly.showing_community())
        pid = next(iter(self._species()))
        fly._open_member({"id": pid})
        self.assertTrue(fly.page.isVisible())
        self.assertFalse(fly.community.isVisible())
        self.assertTrue(fly._back.isVisible())
        self.assertIn(self.community["name"], fly._back.text())
        self.assertEqual(fly.page.shown_id(), pid)
        fly.back_to_community()
        self.assertTrue(fly.community.isVisible())
        self.assertFalse(fly._back.isVisible())
        # A plant opened from the plant list has no way back to a community.
        fly.show_plant({"id": pid})
        self.assertFalse(fly._back.isVisible())
        self.assertFalse(fly.showing_community())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheListOpensIt(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-community"])
        _plants_mod.init_db()

    def _first_community(self, panel):
        tree = panel.polyculture_tree
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QTreeWidgetItemIterator
        it = QTreeWidgetItemIterator(tree)
        while it.value() is not None:
            item = it.value()
            if item.data(0, Qt.ItemDataRole.UserRole) is not None:
                return item
            it += 1
        self.fail("no community in the list")

    def test_choosing_opens_the_page_except_while_placing(self):
        from src.polyculture_panel import PolyculturePanel
        panel = PolyculturePanel()
        self.addCleanup(panel.close)
        item = self._first_community(panel)
        index = panel.polyculture_tree.indexFromItem(item)
        asked = []
        panel.page_requested.connect(asked.append)
        panel._on_list_choose(index)
        self.assertEqual(len(asked), 1)
        panel._armed = True                 # the list is a palette now
        panel._on_list_choose(index)
        self.assertEqual(len(asked), 1, "a page opened while placing")


if __name__ == "__main__":
    unittest.main()
