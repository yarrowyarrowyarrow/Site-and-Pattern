"""
tests/test_species_page.py — a plant's page, and when it opens (F192, V3.00).

The page replaced a card painted into the list row: drawn at an estimated
height, so Saskatoon Berry's 26 animals stopped at the seventh and the next
line drew over them, unselectable and silent to a screen reader. These check
the page is labels a reader can select and hear, that it carries what the card
had, and the gestures that open and close it beside the Browse list.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_page_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _app():
    return QApplication.instance() or QApplication(["permadesign-tests"])


def _saskatoon():
    from src.db.plants import search_plants
    return next(r for r in search_plants(query="saskatoon")
                if r["common_name"] == "Saskatoon Berry")


def _texts(widget):
    return [label.text() for label in widget.findChildren(QLabel)]


class TestTheCalendarLine(unittest.TestCase):
    """Qt-free helpers; the module imports Qt, so they skip with it."""

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_months_read_as_runs(self):
        from src.species_page import _month_runs
        self.assertEqual(_month_runs([3, 4]), "March and April")
        self.assertEqual(_month_runs([5, 6, 7]), "May to July")
        self.assertEqual(_month_runs([3, 5, 6, 7, 10]),
                         "March, May to July, October")

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_only_tasks_the_windows_do_not_already_say(self):
        from src.species_page import _calendar_tasks
        cal = [{"month": 5, "status": "growing"}, {"month": 7, "status": "harvest"},
               {"month": 3, "status": "pruning"}, {"month": 4, "status": "pruning"}]
        self.assertEqual(_calendar_tasks(cal, edible=False), "Prune in March and April")
        self.assertEqual(_calendar_tasks(cal, edible=True),
                         "Prune in March and April · Harvest in July")
        self.assertEqual(_calendar_tasks([{"month": 6, "status": "growing"}],
                                         edible=True), "")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestThePage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.species_page import SpeciesPage
        self.page = SpeciesPage(actions=True, closable=True)
        self.addCleanup(self.page.deleteLater)
        self.page.resize(400, 700)
        self.row = _saskatoon()
        self.page.show_plant(self.row, placed=2)

    def test_it_says_what_the_card_said_and_what_it_did_not(self):
        texts = " ".join(_texts(self.page))
        for want in ("Saskatoon Berry", "Amelanchier alnifolia",
                     "2 in this design", "Roles", "Pollinator Support",
                     "Conditions", "Season", "Wildlife", "Found in"):
            self.assertIn(want, texts)

    def test_every_animal_is_reachable_and_counted_once(self):
        """26 relationships, 25 animals: one of them takes two things from
        the plant. The card stopped at seven; every group here ends in a link
        to the rest when it is long."""
        entry = self.page.entry()
        w = entry["wildlife"]
        self.assertEqual(w["total"], 26)
        self.assertEqual(w["animals"], 25)
        texts = " ".join(_texts(self.page))
        self.assertIn("Feeds or shelters 25 documented species", texts)
        long = next(g for g in w["groups"] if len(g["items"]) > 8)
        label = next(l for l in self.page.findChildren(QLabel)
                     if l.text().startswith(f"<b>{long['how']}</b>"))
        last = long["items"][-1]["name"]
        self.assertNotIn(last, label.text())
        self.assertIn("more</a>", label.text())
        label.linkActivated.emit("more")
        self.assertIn(last, label.text())
        self.assertNotIn("more</a>", label.text())

    def test_every_line_can_be_selected(self):
        """The painted card's text could not be selected, copied or zoomed."""
        lines = [l for l in self.page.findChildren(QLabel) if l.text()]
        self.assertGreater(len(lines), 10)
        for label in lines:
            self.assertTrue(
                label.textInteractionFlags()
                & Qt.TextInteractionFlag.TextSelectableByMouse,
                label.text()[:40])

    def test_the_season_bar_is_named_with_the_sentence(self):
        from src.species_page import SeasonBar
        bar = self.page.findChild(SeasonBar)
        self.assertIsNotNone(bar)
        self.assertEqual(bar.accessibleName(), "Flowers May to June; fruits July to August")
        self.assertEqual(bar.toolTip(), bar.accessibleName())

    def test_place_and_mix_hand_back_the_row(self):
        placed, mixed = [], []
        self.page.place_requested.connect(placed.append)
        self.page.mix_requested.connect(mixed.append)
        place = self.page.findChild(QWidget, "placeButton")
        self.assertEqual(place.accessibleName(),
                         "Place Saskatoon Berry on the map")
        place.click()
        self.page.findChild(QWidget, "speciesPageMix").click()
        self.assertEqual([p["id"] for p in placed], [self.row["id"]])
        self.assertEqual([p["id"] for p in mixed], [self.row["id"]])

    def test_in_the_mix_says_so_and_cannot_be_added_twice(self):
        self.page.set_placement(in_mix=True)
        mix = self.page.findChild(QWidget, "speciesPageMix")
        self.assertEqual(mix.text(), "In the mix")
        self.assertFalse(mix.isEnabled())

    def test_esc_asks_to_close(self):
        closed = []
        self.page.close_requested.connect(lambda: closed.append(1))
        QTest.keyClick(self.page, Qt.Key.Key_Escape)
        self.assertEqual(closed, [1])

    def test_the_same_plant_keeps_its_place_a_new_one_starts_at_the_top(self):
        bar = self.page._scroll.verticalScrollBar()
        self.page.show()
        self._app.processEvents()
        bar.setValue(bar.maximum())
        if bar.value() == 0:
            self.skipTest("the page fits without scrolling here")
        self.page.show_plant(self.row, placed=3)
        self.assertGreater(bar.value(), 0)
        from src.db.plants import search_plants
        self.page.show_plant(search_plants(query="yarrow")[0])
        self.assertEqual(bar.value(), 0)

    def test_an_unknown_plant_empties_the_page(self):
        self.page.show_plant({"id": 999999})
        self.assertEqual(self.page.shown_id(), 0)
        self.assertIn("Pick a species to read about it.", _texts(self.page))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheFlyout(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.species_flyout import SpeciesFlyout
        self.column = QWidget()
        self.addCleanup(self.column.deleteLater)
        col = QVBoxLayout(self.column)
        col.setContentsMargins(0, 0, 0, 0)
        self.map = QWidget()
        col.addWidget(self.map)
        self.column.resize(913, 623)
        self.column.show()
        self.fly = SpeciesFlyout(self.column, anchor=self.map)
        self._app.processEvents()

    def test_it_sits_against_the_maps_right_edge(self):
        self.fly.show_plant(_saskatoon())
        g, m = self.fly.geometry(), self.map.geometry()
        self.assertTrue(self.fly.isVisible())
        self.assertEqual(g.right(), m.right() - 8)
        self.assertEqual(g.top(), m.top() + 8)
        self.assertLessEqual(g.width(), max(300, int(m.width() * 0.45)))
        self.assertEqual(g.height(), m.height() - 16)

    def test_it_is_the_maps_sibling_not_its_child(self):
        """A child of the web view never reaches the accessibility tree."""
        self.assertIs(self.fly.parentWidget(), self.column)
        self.assertEqual(self.fly.accessibleName(), "Plant page")

    def test_it_follows_the_map_when_the_window_changes_size(self):
        self.fly.show_plant(_saskatoon())
        self.column.resize(1300, 800)
        self._app.processEvents()
        self._app.processEvents()
        self.assertEqual(self.fly.geometry().right(),
                         self.map.geometry().right() - 8)

    def test_focus_lands_on_place(self):
        self.column.activateWindow()
        self.fly.show_plant(_saskatoon(), focus=True)
        self.assertIs(self.fly.focusWidget(),
                      self.fly.page.findChild(QWidget, "placeButton"))


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestWhenTheBrowseListOpensAPage(unittest.TestCase):
    """Choosing shows the page; placing closes it; nothing opens it while the
    map is placing (the list is a palette then, V2.99)."""

    @classmethod
    def setUpClass(cls):
        cls._app = _app()
        _plants.init_db()

    def setUp(self):
        from src.plant_panel import PlantPanel
        self.panel = PlantPanel()
        self.addCleanup(self.panel.deleteLater)
        self.panel.resize(437, 760)
        self.panel.show()
        self.requests, self.closes = [], []
        self.panel.page_requested.connect(self.requests.append)
        self.panel.page_closed.connect(lambda: self.closes.append(1))
        self.view = self.panel._results_list
        self.index = self.view.model().index(3, 0)

    def _click(self, index):
        rect = self.view.visualRect(index)
        QTest.mouseClick(self.view.viewport(), Qt.MouseButton.LeftButton,
                         pos=rect.center())

    def test_a_click_shows_the_page_and_arms_nothing(self):
        self._click(self.index)
        self.assertEqual(len(self.requests), 1)
        self.assertFalse(self.requests[0]["focus"])
        self.assertEqual(self.panel.page_plant_id(),
                         self.requests[0]["plant"]["id"])
        self.assertFalse(self.panel._armed)

    def test_an_arrow_steps_the_page_along(self):
        self._click(self.index)
        QTest.keyClick(self.view, Qt.Key.Key_Down)
        self.assertEqual(len(self.requests), 2)
        self.assertNotEqual(self.requests[0]["plant"]["id"],
                            self.requests[1]["plant"]["id"])

    def test_right_arrow_opens_it_with_the_keyboard_inside(self):
        self.view.setCurrentIndex(self.index)
        QTest.keyClick(self.view, Qt.Key.Key_Right)
        self.assertTrue(self.requests[-1]["focus"])

    def test_focus_arriving_opens_nothing(self):
        self.view.setFocus()
        self._app.processEvents()
        self.assertEqual(self.requests, [])

    def test_placing_closes_it_and_choosing_while_placing_opens_nothing(self):
        self._click(self.index)
        QTest.keyClick(self.view, Qt.Key.Key_Return)          # place it
        self.assertTrue(self.panel._armed)
        self.assertEqual(self.closes, [1])
        before = len(self.requests)
        self._click(self.view.model().index(6, 0))            # the palette
        self.assertEqual(len(self.requests), before)
        self.assertEqual(self.panel._armed_plant["id"],
                         self.view.model().index(6, 0).data(
                             Qt.ItemDataRole.UserRole + 1)["id"])

    def test_esc_in_the_list_closes_it_first(self):
        self._click(self.index)
        QTest.keyClick(self.view, Qt.Key.Key_Escape)
        self.assertEqual(self.closes, [1])
        self.assertEqual(self.panel.page_plant_id(), 0)

    def test_leaving_the_tab_closes_it(self):
        self._click(self.index)
        self.panel.hide()
        self.assertEqual(self.closes, [1])

    def test_a_search_that_hides_the_plant_closes_it(self):
        self._click(self.index)
        self.panel.picker.search_box.setText("zzzz no such plant")
        self.panel.picker.refresh()
        self.assertEqual(self.closes, [1])

    def test_adding_to_the_mix_updates_an_open_page(self):
        self._click(self.index)
        plant = self.requests[-1]["plant"]
        self.panel.add_to_mix(plant)
        self.assertTrue(self.requests[-1]["in_mix"])

    def test_the_context_menu_offers_the_page_not_a_card(self):
        import inspect
        src = inspect.getsource(type(self.panel)._on_plant_context_menu)
        self.assertIn('f"About {plant[\'common_name\']}"', src)
        self.assertNotIn("Expand details", src)


if __name__ == "__main__":
    unittest.main()
