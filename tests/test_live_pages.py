"""
tests/test_live_pages.py — the pages that waited for a button fill themselves
(V3.05).

The V3.05 surface audit found five pages opening on a button over an empty box:
Analysis › Habitat (*Calculate Habitat Value*) and Planning › Effort, Wildlife,
Harvest and Water. Each panel already had the design, so the button only gated
work, and its result went stale with the next edit while the page went on
showing it as current. ``src/live_refresh.py`` fills the page on screen; Water's
inputs start from the design (``src/design_inputs.py``).
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_live_pages_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "live_pages.db")

from src.design_inputs import boundary_area_m2, water_features  # noqa: E402

try:
    from PyQt6.QtWidgets import (QApplication, QLabel, QPushButton,
                                 QTabWidget, QWidget)
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


def _square(lat, lng, side_m):
    """A closed [lng, lat] ring ``side_m`` on a side."""
    import math
    dlat = side_m / 111320.0
    dlng = side_m / (111320.0 * math.cos(math.radians(lat)))
    return [[lng, lat], [lng + dlng, lat], [lng + dlng, lat + dlat],
            [lng, lat + dlat], [lng, lat]]


class TestWhatTheDesignKnows(unittest.TestCase):

    def test_the_boundary_area_is_read_off_the_project(self):
        project = {"features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [_square(53.5, -113.5, 10.0)]},
            "properties": {"element_type": "property_boundary"}}]}
        self.assertAlmostEqual(boundary_area_m2(project), 100.0, delta=1.0)

    def test_no_boundary_is_no_area(self):
        self.assertEqual(boundary_area_m2({"features": []}), 0.0)
        self.assertEqual(boundary_area_m2({}), 0.0)

    def test_water_structures_are_counted(self):
        placed = [{"id": "pond"}, {"id": "rain_barrel"}, {"id": "rain_barrel"},
                  {"id": "bee_hotel"}, {"id": "swale"}, {}]
        self.assertEqual(water_features(placed),
                         {"rain_barrels": 2, "ponds": 1, "swales": 1})


def _catalogue_plants(n=4):
    """Real rows, enriched the way app._sync_planning_panel enriches them."""
    from src.db.plants import get_all_plants, init_db
    init_db()
    out = []
    for p in get_all_plants():
        if p.get("plant_type") in ("shrub", "wildflower", "tree"):
            out.append({"plant_id": p["id"], "common_name": p["common_name"],
                        "plant_type": p.get("plant_type"),
                        "water_needs": p.get("water_needs", "medium"),
                        "native_to_alberta": True,
                        "lat": 53.5, "lng": -113.5})
        if len(out) >= n:
            break
    return out


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestLiveRefresh(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-live-tests"])

    def _owner(self):
        from src.live_refresh import LiveRefresh
        owner = QWidget()
        tabs = QTabWidget(owner)
        a, b = QWidget(), QWidget()
        tabs.addTab(a, "A")
        tabs.addTab(b, "B")
        calls = []
        live = LiveRefresh(owner, tabs, {a: lambda: calls.append("a"),
                                         b: lambda: calls.append("b")})
        return owner, tabs, live, calls

    def test_the_page_on_screen_is_filled(self):
        owner, tabs, live, calls = self._owner()
        owner.show()
        live.poke()
        self.assertTrue(live.fill_now())
        self.assertEqual(calls[-1], "a")
        tabs.setCurrentIndex(1)
        live.fill_now()
        self.assertEqual(calls[-1], "b")

    def test_a_panel_nobody_can_see_is_not_computed(self):
        owner, tabs, live, calls = self._owner()
        live.poke()
        self.assertFalse(live.fill_now())
        self.assertEqual(calls, [])

    def test_a_burst_of_edits_is_one_fill(self):
        owner, tabs, live, calls = self._owner()
        owner.show()
        for _ in range(8):
            live.poke()
        import time
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not calls:
            self._app.processEvents()
        for _ in range(20):
            self._app.processEvents()
        self.assertEqual(calls, ["a"])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestThePagesFillThemselves(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-live-tests"])
        cls._plants = _catalogue_plants()

    def _buttons(self, panel):
        return [b.text() for b in panel.findChildren(QPushButton)]

    def test_no_calculate_buttons_are_left(self):
        from src.analysis_panel import AnalysisPanel
        from src.planning_panel import PlanningPanel
        words = " ".join(self._buttons(PlanningPanel())
                         + self._buttons(AnalysisPanel()))
        for gone in ("Calculate Habitat Value", "Calculate Establishment",
                     "Show Wildlife Forage", "Show Human Forage"):
            self.assertNotIn(gone, words)

    def test_the_habitat_score_follows_the_design(self):
        from src.analysis_panel import AnalysisPanel
        panel = AnalysisPanel()
        panel.resize(420, 700)
        panel.show()
        panel._tabs.setCurrentWidget(panel._habitat_page)
        panel.set_placed_plants(self._plants)
        panel._live.fill_now()
        first = panel._habitat_score_label.text()
        self.assertRegex(first, r"^\d+ / 100$")
        panel.set_placed_plants([])
        panel._live.fill_now()
        self.assertEqual(panel._habitat_score_label.text(), "—",
                         "an emptied design kept its old score")
        panel.close()

    def test_every_planning_page_fills_on_screen(self):
        from src.planning_panel import PlanningPanel
        panel = PlanningPanel()
        panel.resize(420, 700)
        panel.show()
        panel.set_placed_plants(self._plants)
        for page, check in (
                (panel._maint_page, lambda: panel._maint_results.text()),
                (panel._water_page, lambda: panel._water_results.text()),
        ):
            panel._tabs.setCurrentWidget(page)
            panel._live.fill_now()
            self.assertTrue(check(), f"page {panel._tabs.tabText(panel._tabs.indexOf(page))} "
                                     "stayed empty")
        panel.close()

    def test_food_fills_on_screen(self):
        from src.analysis_panel import AnalysisPanel
        panel = AnalysisPanel()
        panel.resize(420, 700)
        panel.show()
        panel._tabs.setCurrentWidget(panel._food)
        panel.set_placed_plants(self._plants)
        self.assertTrue(panel._live.fill_now())
        self.assertIn("Your plants feed", panel._food._summary_line.text())
        panel.close()

    def test_a_live_page_moved_to_another_strip_is_still_filled(self):
        """V3.08 moved Planning's pages into Design: the refill follows the
        strip they are in, and the one they left no longer drives it."""
        from PyQt6.QtWidgets import QLabel, QTabWidget, QWidget
        from src.live_refresh import LiveRefresh
        old_owner, new_owner = QWidget(), QWidget()
        old_tabs, new_tabs = QTabWidget(old_owner), QTabWidget(new_owner)
        page, other = QLabel("page"), QLabel("other")
        old_tabs.addTab(page, "Page")
        filled = []
        live = LiveRefresh(old_owner, old_tabs, {page: lambda: filled.append(1)})
        old_tabs.removeTab(0)
        new_tabs.addTab(other, "Other")
        new_tabs.addTab(page, "Page")
        live.move_to(new_owner, new_tabs, {page: lambda: filled.append(2)})
        new_owner.show()
        new_tabs.setCurrentWidget(page)
        self.assertTrue(live.fill_now())
        self.assertEqual(filled, [2])
        new_tabs.setCurrentWidget(other)
        self.assertFalse(live.fill_now())
        old_tabs.addTab(QLabel("left behind"), "Old")    # fires currentChanged
        old_owner.show()
        self.assertFalse(live._timer.isActive(),
                         "the strip it left still pokes it")
        new_owner.close()
        old_owner.close()

    def test_every_type_in_the_design_has_its_row_in_the_hours(self):
        """Until V3.08 the table listed six fixed types, so wildflowers and
        grasses were in the subtotal with no row of their own: a worked example
        showed 17 hours of rows over a 55-hour subtotal."""
        import re
        from src.planning_panel import PlanningPanel
        panel = PlanningPanel()
        panel.set_placed_plants([
            {"plant_id": 1, "plant_type": "wildflower", "native_to_alberta": 1},
            {"plant_id": 2, "plant_type": "grass", "native_to_alberta": 1},
            {"plant_id": 3, "plant_type": "shrub", "native_to_alberta": 1},
            {"plant_id": 4, "plant_type": "rush", "native_to_alberta": 1}])
        panel._calc_maintenance()
        text = panel._maint_results.text()
        for row in ("Wildflowers", "Grasses", "Shrubs", "Rushes"):
            self.assertIn(f">{row}<", text)
        year1 = [float(h) for h in re.findall(r">(\d+(?:\.\d+)?) h<", text)]
        self.assertTrue(year1, text)

    def test_water_starts_from_the_design(self):
        from src.planning_panel import PlanningPanel
        panel = PlanningPanel()
        panel.set_structures([{"id": "pond"}, {"id": "rain_barrel"}])
        panel.set_site_area(88.0)
        self.assertEqual(panel._has_pond.value(), 1)
        self.assertEqual(panel._rain_barrels.value(), 1)
        self.assertEqual(panel._has_swale.value(), 0)
        self.assertAlmostEqual(panel._garden_area.value(), 88.0)
        # No boundary: the area keeps what it had rather than reading 0.
        panel.set_site_area(0.0)
        self.assertAlmostEqual(panel._garden_area.value(), 88.0)

    def test_notes_count_what_was_loaded(self):
        from src.planning_panel import PlanningPanel
        panel = PlanningPanel()
        panel.set_notes("Soil felt like clay near the fence")
        self.assertEqual(panel._notes_count.text(), "7 words")
        panel.set_notes("")
        self.assertEqual(panel._notes_count.text(), "0 words")


if __name__ == "__main__":
    unittest.main()
