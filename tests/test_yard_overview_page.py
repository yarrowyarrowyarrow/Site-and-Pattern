"""
tests/test_yard_overview_page.py — Design › Overview in the real window (OV-2,
OV-9, OV-10, MD-4; V3.27).

The page is the Design tab's first and current page, replaces the Report card
in the simple app, and every button does what its words say: filters on the
plant list, Draw › Shape on the right type, the fill and swap dialogs as one
undo step each, Export PDF, and More detail with the Advanced tools turned on.
"""

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="overview_page_")
import src.db.plants as _plants  # noqa: E402
_plants._DATA_DIR = _TMP
_plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")
try:
    import src.settings as _settings
    _settings._CONFIG_PATH = os.path.join(_TMP, "config.json")
except Exception:                                          # noqa: BLE001
    pass

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                          # noqa: BLE001
    _HAVE_QT = False


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


@unittest.skipUnless(_HAVE_QT, "PyQt6 and PyQt6-WebEngine needed")
class TheOverviewPage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        _plants._DATA_DIR = _TMP
        _plants._DB_PATH = os.path.join(_TMP, "permadesign_test.db")
        from src import advanced_tools
        cls._settings = mock.patch.object(advanced_tools, "is_on",
                                          return_value=False)
        cls._settings.start()
        from src.app import MainWindow
        cls.win = MainWindow()
        cls.win.resize(1366, 768)
        cls.win.show()

    @classmethod
    def tearDownClass(cls):
        cls._settings.stop()
        cls.win._modified = False
        cls.win.close()
        cls.win.deleteLater()

    def setUp(self):
        from src import onboarding_flow
        self.win._modified = False
        with mock.patch.object(onboarding_flow, "example_path",
                               return_value=os.path.join(
                                   _TMP, "example.perma.geojson")):
            onboarding_flow.open_example(self.win)
        self._show()

    def _show(self):
        from src.keyboard_help import show_panel
        show_panel(self.win.overview_page)
        self._app.processEvents()
        # Filled directly: in a full run the window may not count as on
        # screen, and LiveRefresh fills only a page that is.
        from src import yard_overview_flow
        yard_overview_flow.fill(self.win)
        self._app.processEvents()

    def _press(self, key):
        self.win.overview_page.buttons[key].click()
        self._app.processEvents()

    def test_first_and_current_and_the_report_card_waits(self):
        tabs = self.win.analysis_panel._tabs
        self.assertIs(tabs.widget(0), self.win.overview_page)
        self.assertEqual(tabs.tabText(0), "Overview")
        stats = self.win.on_this_design._stats_page
        self.assertFalse(tabs.isTabVisible(tabs.indexOf(stats)))

    def test_six_cards_and_no_sideways_scroll(self):
        page = self.win.overview_page
        self.assertEqual(sorted(page.cards), sorted(
            ["food", "flowers", "native", "cover", "street", "cost"]))
        self.assertEqual(page.horizontalScrollBar().maximum(), 0)
        # Fonts differ by machine (CI's DejaVu is wider): no card may need
        # more than the panel's narrowest width, 320 px less the margins.
        for key, card in page.cards.items():
            self.assertLessEqual(card.minimumSizeHint().width(), 300, key)
        for card in page.cards.values():
            self.assertIn(", ", card.accessibleName())

    def test_the_cost_agrees_with_the_report_card(self):
        """§4 rule 5: one number, one source."""
        from src.sourcing import format_cost
        cost = self.win.on_this_design._cost_breakdown["plants"]
        line = next(it for it in __import__(
            "src.yard_overview_items", fromlist=["x"]).overview(
                self.win._project) if it.key == "cost").lines[0]
        self.assertIn(format_cost(*cost), line)

    def test_find_an_october_flower_sets_the_filter(self):
        self._press("flowers")
        picker = self.win.plant_panel.picker
        self.assertEqual(picker.combos["bloom_months"].checked_keys(), ["10"])
        picker.set_facet("bloom_months", [])

    def test_draw_a_mown_strip_opens_shape_on_lawn(self):
        self._press("street")
        tool = self.win.toolbar.shape_tool
        self.assertEqual(tool._type.currentText(), "Lawn Area")
        self.win.toolbar._shape_btn.menu().close()

    def test_print_calls_export(self):
        with mock.patch.object(self.win, "_on_export_pdf") as export:
            self._press("cost")
        export.assert_called_once()

    def test_more_detail_turns_advanced_on_and_shows_food(self):
        from src import advanced_tools_flow, yard_overview_flow
        with mock.patch.object(advanced_tools_flow, "set_and_apply") as on:
            yard_overview_flow.run_action(self.win, "advanced:food")
        on.assert_called_once_with(self.win, True)

    def test_fill_the_gaps_is_one_undo_step(self):
        from src import yard_overview, yard_overview_dialogs
        before = len(self.win._placed_plants)
        plan = yard_overview.fill_plan(self.win._project)
        self.assertGreater(len(plan["records"]), 50)

        def plant(dialog):
            dialog.buttons["plant"].click()
            return 1
        with mock.patch.object(yard_overview_dialogs, "_exec", plant):
            self._press("cover")
        self.assertEqual(len(self.win._placed_plants),
                         before + len(plan["records"]))
        # The plan's acceptance: the item turns Looks good (70%, O3).
        self.assertGreaterEqual(yard_overview.cover(
            self.win._project)["share"], yard_overview.WELL_FILLED)
        self._show()
        item = self.win.overview_page.cards["cover"]
        self.assertIn("Looks good", item.accessibleName())
        self.win._do_undo()
        self.assertEqual(len(self.win._placed_plants), before)

    def test_swap_replaces_where_they_stand_in_one_undo(self):
        from src import yard_overview_dialogs
        from src.db.plants import get_all_plants
        from src import native_here
        names = native_here.native_names("edmonton")
        away = next(r for r in get_all_plants()
                    if r["scientific_name"] not in names
                    and r["plant_type"] == "wildflower")
        target = self.win._placed_plants[3]
        spots = [(p["lat"], p["lng"]) for p in self.win._placed_plants
                 if p["plant_id"] == target["plant_id"]]
        yard_overview_dialogs.replace(self.win, target["plant_id"],
                                      away["id"])
        self.win._sync_planning_panel()
        self._show()
        from src.yard_overview_items import overview
        native = next(it for it in overview(self.win._project)
                      if it.key == "native")
        self.assertEqual(native.target, f"swap:{away['id']}")
        choices = yard_overview_dialogs.swap_choices(self.win, away["id"])
        for swap in choices:
            self.assertIn(_plants.get_plant(swap.plant_id)["scientific_name"],
                          names)
        if not choices:
            self.skipTest("no native substitute recorded for "
                          + away["common_name"])
        new = choices[0].plant_id
        had = [(p["lat"], p["lng"]) for p in self.win._placed_plants
               if p["plant_id"] == new]

        def pick(dialog):
            dialog.buttons[str(new)].click()
            return 1
        with mock.patch.object(yard_overview_dialogs, "_exec", pick):
            self._press("native")
        placed = [(p["lat"], p["lng"]) for p in self.win._placed_plants
                  if p["plant_id"] == new]
        self.assertEqual(sorted(placed), sorted(had + spots))
        self.assertFalse(any(p["plant_id"] == away["id"]
                             for p in self.win._placed_plants))
        self.win._do_undo()
        self.assertTrue(any(p["plant_id"] == away["id"]
                            for p in self.win._placed_plants))


if __name__ == "__main__":
    unittest.main()
