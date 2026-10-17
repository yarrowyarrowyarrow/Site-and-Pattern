"""
tests/test_homeowner_path.py — the usability session's seven tasks, walked
through the real window before five people walk them (FN-9, V3.32;
docs/homeowner/01-personas.md §6).

The sessions are the only test of whether the plan worked, and they cost five
people's evenings. A task that cannot be done at all should not be found by
them. So each task here is done the way the session's script asks for it, in
the simple app, through the controls a person would press: the address box
and its list, the Draw row's shape, *Plan my yard* in the strip, the Overview,
a plant clicked on the map and its page, Share's exports, Save and the start
screen's list. Where a control's result comes back from the map page (the pin,
a finished outline), the test hands Python what the page would.

It cannot say whether a person finds the control. That is what the sessions
are for; this only says every task has a way through.
"""

import json
import math
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_homeowner_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "t.db")
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = os.path.join(_TMP, "config.json")
except Exception:  # pragma: no cover
    pass

#: Strathcona, Edmonton: a house lot inside the region pack.
PIN = (53.5170, -113.4990)
ADDRESS = "10423 81 Avenue NW, Strathcona, Edmonton, Alberta, T6E 1X3, Canada"


def _qt_available():
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _offset(lat, lng, north_m, east_m):
    return (lat + north_m / 111_320.0,
            lng + east_m / (111_320.0 * math.cos(math.radians(lat))))


def _inside(pt, ring):
    """Even-odd test, ``ring`` as ``[(lat, lng), ...]``."""
    y, x = pt
    inside = False
    for (y1, x1), (y2, x2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


@unittest.skipUnless(_qt_available(), "needs PyQt6 and PyQt6-WebEngine")
class TheSevenTasks(unittest.TestCase):
    """One window, the tasks in the session's order: each builds on the last,
    as it does for the person at the laptop."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["homeowner-path"])
        from src import saves
        cls.saves_dir = os.path.join(_TMP, "saves")
        os.makedirs(cls.saves_dir, exist_ok=True)
        cls._saves_dir = saves.saves_dir
        saves.saves_dir = lambda: cls.saves_dir
        saves.clear_cache()
        from src import property_data
        cls._cache = property_data._GEOCODE_CACHE_SIZE
        try:
            from src.app import MainWindow
            cls.win = MainWindow()
        except Exception as exc:  # noqa: BLE001
            cls.win = None
            cls.error = exc
        else:
            cls.win.resize(1366, 768)
            cls.win.show()
            cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        from src import saves
        saves.saves_dir = cls._saves_dir
        saves.clear_cache()
        if cls.win is not None:
            cls.win._modified = False
            cls.win.close()
            cls.win.deleteLater()
            cls.win = None
        shutil.rmtree(_TMP, ignore_errors=True)

    def setUp(self):
        if self.win is None:
            self.skipTest(f"MainWindow could not be built here: {self.error}")
        from src import advanced_tools
        if advanced_tools.is_on():
            self.skipTest("the sessions run in the simple app")

    # ── helpers ─────────────────────────────────────────────────────────────

    def _bed_ring(self):
        """An 8 m × 4 m bed in the front yard, 6 m south of the pin."""
        lat, lng = PIN
        corners = [(-6, -4), (-6, 4), (-10, 4), (-10, -4)]
        return [_offset(lat, lng, n, e) for n, e in corners]

    def _page_text(self, page) -> str:
        from PyQt6.QtWidgets import QLabel
        return "\n".join(lbl.text() for lbl in page.findChildren(QLabel)
                         if lbl.text())

    def _plan(self):
        """Press Plan my yard, take the dialog's defaults, and run the plan
        here rather than on a thread."""
        from PyQt6.QtWidgets import QDialog
        from src.controllers import generation
        from src.generate_worker import GenerateWorker
        ctl = self.win._generation

        def run_now(_self, **kw):
            worker = GenerateWorker(**kw)
            got = {}
            worker.finished.connect(lambda p: got.setdefault("project", p))
            worker.failed.connect(lambda m: got.setdefault("error", m))
            worker.run()
            self.assertNotIn("error", got, got.get("error"))
            _self._on_finished(got["project"])

        seen = {}

        def accept(dlg):
            seen["dialog"] = dlg
            return QDialog.DialogCode.Accepted
        with mock.patch.object(generation.GenerationController, "_exec",
                               staticmethod(accept)), \
                mock.patch.object(generation.GenerationController, "_start",
                                  run_now):
            self.win.first_step_bar._generate.click()
        self.app.processEvents()
        return seen.get("dialog"), ctl

    # ── the tasks ───────────────────────────────────────────────────────────

    def test_1_to_7_in_order(self):
        """unittest runs methods alphabetically; the tasks need their order,
        so they are one test with a step per task."""
        self._task_1_start_a_plan()
        self._task_2_get_a_suggestion()
        self._task_3_the_street()
        plant_id = self._task_4_caterpillars_and_height()
        self._task_5_swap(plant_id)
        self._task_6_the_nursery()
        self._task_7_come_back()

    def _task_1_start_a_plan(self):
        """*Start a plan for your yard.* A pin on the yard and a bed."""
        from src import start_flow
        win, sp = self.win, self.win.site_panel
        start_flow.start_new_yard(win)
        # The address box, Find, the list, a click on the match.
        sp._addr_input.setText("10423 81 Ave")
        with mock.patch.object(sp, "_run_geocode") as run:
            sp._btn_search.click()
        run.assert_called_once()
        sp._on_geocode_results([{"label": ADDRESS, "lat": PIN[0],
                                 "lng": PIN[1]}])
        self.assertTrue(sp._addr_results.isVisible())
        placed = []
        with mock.patch.object(win.map_widget, "place_site_pin",
                               lambda *a: placed.append(a)):
            sp._on_address_pick(sp._addr_results.item(0))
        self.assertEqual(placed[0][:2], PIN)
        # The page answers with site_pin_placed; no fetch leaves the machine.
        with mock.patch.object(sp, "_start_fetch"):
            win._map_events._on_site_pin_placed(*PIN, ADDRESS)
        sc = win._project["properties"]["site_config"]
        self.assertEqual((sc["latitude"], sc["longitude"]), PIN)
        self.assertEqual(win._project["properties"]["project_name"],
                         "10423 81 Avenue NW",
                         "the design takes its address's name (ST-5)")
        # Draw › Shape: the Draw row's button, Garden Bed, Draw on the map.
        ring = self._bed_ring()
        win._map_events._on_shape_complete(
            "bed-1", json.dumps([list(p) for p in ring]), "", "Garden Bed",
            "#4caf50", "#2e7d32", 0.25, "", 32.0)
        from src import onboarding
        progress = onboarding.steps_progress(win._project)
        self.assertTrue(all(step["done"] for step in progress[:2]),
                        [(s["key"], s["done"]) for s in progress])
        self.assertTrue(win.first_step_bar._generate.isEnabled())

    def _task_2_get_a_suggestion(self):
        """*Get the app to suggest a planting.* A plan in the drawn bed."""
        dialog, _ctl = self._plan()
        self.assertIsNotNone(dialog, "Plan my yard opened no dialog")
        plants = self.win._placed_plants
        self.assertGreaterEqual(len(plants), 4, "a bed of 32 m² got a plan")
        ring = self._bed_ring()
        outside = [p for p in plants
                   if not _inside((p["lat"], p["lng"]), ring)]
        self.assertEqual(outside, [], "the plan planted outside the bed")
        bar = self.win.plan_bar
        self.assertTrue(bar.isVisible())
        self.assertIn("Your plan:", self._page_text(bar))

    def _task_3_the_street(self):
        """*Is this going to look messy from the street? What would help?*
        The Overview's street item, with a sign of care and a next step."""
        from src.yard_overview_items import overview
        street = next(it for it in overview(self.win._project)
                      if it.key == "street")
        text = " ".join(street.lines)
        self.assertIn("signs of care", text)
        from src import yard_overview_flow
        yard_overview_flow.fill(self.win)
        self.assertIn(street.title, self._page_text(self.win.overview_page))

    def _task_4_caterpillars_and_height(self) -> int:
        """*Find a plant in your plan that will feed caterpillars, and tell
        me how tall it gets.* A plant clicked on the map opens its page,
        which says both."""
        from src import species_flyout
        fly = self.win.species_flyout
        tried = []
        for p in self.win._placed_plants:
            pid = p["plant_id"]
            if pid in tried:
                continue
            tried.append(pid)
            self.assertTrue(species_flyout.on_plant_clicked(
                self.win, pid, p["lat"], p["lng"]))
            text = self._page_text(fly.page)
            if "caterpillar" in text.lower():
                self.assertRegex(text, r"\d+(\.\d+)?\s*(cm|m)\b",
                                 "the page says how tall it gets")
                return pid
        self.fail("no plant in the plan says on its page that it feeds "
                  "caterpillars")

    def _task_5_swap(self, plant_id: int):
        """*Swap one plant you don't like for another that suits the same
        spot.* The page's Swap…, one choice, one undo step."""
        from src import yard_overview_dialogs
        fly = self.win.species_flyout
        swap = fly.page._swap_btn
        self.assertTrue(swap.isVisibleTo(fly.page),
                        "a placed plant's page offers Swap…")
        choices = yard_overview_dialogs.swap_choices(self.win, plant_id)
        if not choices:
            self.skipTest("no plant recorded as doing a similar job")
        new = choices[0].plant_id
        spots = sorted((p["lat"], p["lng"]) for p in self.win._placed_plants
                       if p["plant_id"] == plant_id)

        def pick(dialog):
            self.assertNotIn("is not", self._page_text(dialog),
                             "a native plant is not called not native")
            dialog.buttons[str(new)].click()
            return 1
        with mock.patch.object(yard_overview_dialogs, "_exec", pick):
            swap.click()
        moved = sorted((p["lat"], p["lng"]) for p in self.win._placed_plants
                       if p["plant_id"] == new)
        self.assertTrue(set(spots) <= set(moved))
        self.assertEqual(fly.page.shown_id(), new)
        self.win._do_undo()
        back = sorted((p["lat"], p["lng"]) for p in self.win._placed_plants
                      if p["plant_id"] == plant_id)
        self.assertEqual(back, spots, "Undo puts it back")

    def _task_6_the_nursery(self):
        """*You're going to the nursery on Saturday. Get what you'll need.*
        Share's Export PDF and Order file, each to a file."""
        share = self.win.share_panel
        pdf = os.path.join(_TMP, "plan.pdf")
        order = os.path.join(_TMP, "order.csv")
        import src.app as app_mod
        from PyQt6.QtWidgets import QFileDialog
        with mock.patch.object(app_mod.QFileDialog, "getSaveFileName",
                               return_value=(pdf, "")), \
                mock.patch.object(app_mod.QMessageBox, "critical",
                                  side_effect=AssertionError):
            share.buttons["Export PDF…"].click()
        self.assertGreater(os.path.getsize(pdf), 10_000)
        with mock.patch.object(QFileDialog, "getSaveFileName",
                               return_value=(order, "")):
            share.buttons["Order file…"].click()
        with open(order, encoding="utf-8") as f:
            text = f.read()
        from src.db.plants import get_plant
        some = get_plant(self.win._placed_plants[0]["plant_id"])
        self.assertIn(some["common_name"], text)

    def _task_7_come_back(self):
        """*Close the app. Next week, come back to this yard.* Save, and the
        start screen's first row opens it."""
        from src import saves, start_flow
        win = self.win
        n = len(win._placed_plants)
        win._on_save()
        self.assertFalse(win._modified)
        saves.clear_cache()
        rows, _total = start_flow.screen_designs(directory=self.saves_dir)
        self.assertTrue(rows, "the start screen lists the saved design")
        self.assertEqual(rows[0]["name"], "10423 81 Avenue NW")
        start_flow.start_new_yard(win)
        self.assertEqual(len(win._placed_plants), 0)
        self.assertTrue(start_flow.dispatch(
            win, start_flow.path_choice(rows[0]["path"])))
        self.assertEqual(len(win._placed_plants), n)
        sc = win._project["properties"]["site_config"]
        self.assertEqual((sc["latitude"], sc["longitude"]), PIN)


if __name__ == "__main__":
    unittest.main()
