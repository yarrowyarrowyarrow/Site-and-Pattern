"""
tests/test_sun_shade.py — sun and shade as one surface (V2.38).

User feedback, second round: "Sunlight analysis needs work… it should mix with
the shade so you can see the sun casting the shadows across the day."

The maths was never the problem — ``solar.sun_position`` already backed the 2D
map, the 3D scene and the fork, and ``solar.KEY_DATES`` already fed *both* date
pickers. The problem was that there were two pickers, on two tabs, and no way
to make them agree except by setting each one. On top of that the arc would not
draw at all until you had pressed a button *and* found the right bit of map to
click.

What these tests hold down:

  * one date and one clock produce the arc's instant and the shade's instant;
  * a scrub never conjures a shade overlay that was not already showing;
  * the arc centres itself on the property, and "Move…" is still there;
  * the clock spans that date's real daylight, never an invented 5-to-9.
"""

import ast
import os
import pathlib
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except Exception:                                    # noqa: BLE001
    _HAVE_QT = False

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"


# ── The Qt-free core ────────────────────────────────────────────────────────

class TestDateVocabulary(unittest.TestCase):
    def test_every_key_date_is_offered_plus_today(self):
        from src import sun_shade
        from src.solar import KEY_DATES
        choices = sun_shade.date_choices()
        self.assertEqual(len(choices), len(KEY_DATES) + 1)
        self.assertEqual([c[0] for c in choices[:-1]], list(KEY_DATES))
        self.assertEqual(choices[-1], ("Today", sun_shade.TODAY))

    def test_a_key_date_resolves_to_that_calendar_day(self):
        from src import sun_shade
        d = sun_shade.resolve_date((6, 21))
        self.assertEqual((d.month, d.day), (6, 21))

    def test_today_is_resolved_when_read_not_when_built(self):
        """A session can outlive midnight; a fixed (month, day) cannot."""
        from src import sun_shade
        self.assertEqual(
            sun_shade.resolve_date(sun_shade.TODAY, today=date(2031, 3, 4)),
            date(2031, 3, 4))

    def test_a_date_that_does_not_exist_falls_back_to_today(self):
        from src import sun_shade
        # Feb 29 in a non-leap seed year — better today's real sun than a crash.
        self.assertEqual(
            sun_shade.resolve_date((2, 30), today=date(2026, 8, 2)),
            date(2026, 8, 2))

    def test_the_panel_opens_in_the_season_you_are_standing_in(self):
        from src import sun_shade
        from src.solar import KEY_DATES
        labels = list(KEY_DATES)
        self.assertEqual(
            labels[sun_shade.nearest_key_date_index(date(2026, 6, 25))],
            "Summer Solstice")
        self.assertEqual(
            labels[sun_shade.nearest_key_date_index(date(2026, 12, 28))],
            "Winter Solstice")

    def test_the_nearest_date_wraps_around_new_year(self):
        """Jan 2 is ten days from the Winter Solstice, not 355."""
        from src import sun_shade
        from src.solar import KEY_DATES
        labels = list(KEY_DATES)
        self.assertEqual(
            labels[sun_shade.nearest_key_date_index(date(2027, 1, 2))],
            "Winter Solstice")


class TestDaylightWindow(unittest.TestCase):
    # NOTE: solar.sunrise_sunset returns LOCAL SOLAR time, not clock time —
    # noon is when the sun is highest, so an Edmonton summer day reads
    # ~03:36–20:38 rather than the 05:04–22:07 MDT on a phone. The *length* is
    # right (17h02 against a real 17h05); the offset is the timezone and DST,
    # which this module has never modelled. These assert the length.

    def test_a_june_day_in_edmonton_is_long(self):
        from src import sun_shade
        lo, hi = sun_shade.daylight_window(53.55, -113.49, date(2025, 6, 21))
        self.assertGreater(hi - lo, 16 * 60)     # real: 17h05
        self.assertLess(hi - lo, 18 * 60)

    def test_a_december_day_in_edmonton_is_short(self):
        from src import sun_shade
        lo, hi = sun_shade.daylight_window(53.55, -113.49, date(2025, 12, 21))
        self.assertGreater(hi - lo, 7 * 60)      # real: 7h27
        self.assertLess(hi - lo, 8 * 60)
        self.assertGreater(lo, 8 * 60)           # a late, short winter day
        self.assertLess(hi, 17 * 60)

    def test_no_location_yet_gives_the_generic_window(self):
        from src import sun_shade
        self.assertEqual(sun_shade.daylight_window(None, None, date(2025, 6, 1)),
                         sun_shade.DEFAULT_WINDOW)

    def test_the_window_is_never_inverted(self):
        """The far north in December has no ordinary sunrise; the honest answer
        is the generic window, not a backwards range a slider cannot hold."""
        from src import sun_shade
        for lat in (53.5, 68.0, 78.0, -80.0):
            for d in (date(2025, 6, 21), date(2025, 12, 21)):
                lo, hi = sun_shade.daylight_window(lat, -113.0, d)
                self.assertLess(lo, hi, f"{lat} on {d}")
                self.assertGreaterEqual(lo, 0)
                self.assertLess(hi, 24 * 60)

    def test_clamping_keeps_a_reading_inside_its_day(self):
        from src import sun_shade
        self.assertEqual(sun_shade.clamp_to_window(3 * 60, (540, 960)), 540)
        self.assertEqual(sun_shade.clamp_to_window(23 * 60, (540, 960)), 960)
        self.assertEqual(sun_shade.clamp_to_window(700, (540, 960)), 700)

    def test_the_clock_reads_as_a_clock(self):
        from src import sun_shade
        self.assertEqual(sun_shade.clock(0), "00:00")
        self.assertEqual(sun_shade.clock(15 * 60), "15:00")
        self.assertEqual(sun_shade.clock(18 * 60 + 30), "18:30")


class TestLeafOff(unittest.TestCase):
    def test_it_reads_the_shade_modules_own_month_set(self):
        """Restating the months here would let the note and the model drift."""
        from src import sun_shade
        from src.shade import _LEAF_OFF_MONTHS
        for m in range(1, 13):
            self.assertEqual(sun_shade.is_leaf_off(m), m in _LEAF_OFF_MONTHS)

    def test_no_month_is_not_leaf_off(self):
        from src import sun_shade
        self.assertFalse(sun_shade.is_leaf_off(None))


class TestCasterInventory(unittest.TestCase):
    @staticmethod
    def _project(*element_types):
        return {"features": [{"properties": {"element_type": t}}
                             for t in element_types]}

    def test_it_counts_marked_trees_and_buildings(self):
        from src import sun_shade
        proj = self._project("existing_tree", "existing_tree",
                             "existing_building", "plant")
        self.assertEqual(sun_shade.caster_counts(proj), (1, 2))

    def test_a_drawn_shape_counts_by_its_caster_kind(self):
        from src import sun_shade
        proj = {"features": [
            {"properties": {"element_type": "custom_shape",
                            "cast_shade": True, "caster_kind": "tree"}},
            {"properties": {"element_type": "custom_shape",
                            "cast_shade": True}},
            {"properties": {"element_type": "custom_shape"}},   # casts nothing
            {"properties": {"element_type": "canopy_footprint",
                            "caster_kind": "tree"}},
        ]}
        self.assertEqual(sun_shade.caster_counts(proj), (1, 2))

    def test_an_empty_project_says_so_rather_than_showing_zeroes(self):
        from src import sun_shade
        text, have = sun_shade.caster_summary(0, 0)
        self.assertFalse(have)
        self.assertIn("No existing features", text)

    def test_the_line_is_singular_when_there_is_one(self):
        from src import sun_shade
        text, have = sun_shade.caster_summary(1, 1)
        self.assertTrue(have)
        self.assertIn("1 building ", text)
        self.assertNotIn("1 buildings", text)
        self.assertNotIn("1 trees", text)

    def test_the_two_surfaces_point_at_the_right_place(self):
        """Same formatter, different signpost — Site says 'here', Analysis
        sends you to Site."""
        from src import sun_shade
        self.assertIn("this tab", sun_shade.caster_summary(0, 0, "this tab")[0])
        self.assertIn("Site → Features",
                      sun_shade.caster_summary(0, 0, "Site → Features")[0])


class TestDefaultAnchor(unittest.TestCase):
    @staticmethod
    def _boundary(ring):
        return {"features": [{
            "properties": {"element_type": "property_boundary"},
            "geometry": {"type": "Polygon", "coordinates": [ring]}}]}

    def test_the_boundary_centroid_wins(self):
        from src import sun_shade
        # GeoJSON is (lng, lat); a closed 20 m-ish square around (53.5, -113.5).
        ring = [[-113.501, 53.499], [-113.499, 53.499],
                [-113.499, 53.501], [-113.501, 53.501], [-113.501, 53.499]]
        lat, lng = sun_shade.default_anchor(
            self._boundary(ring), {"latitude": 10.0, "longitude": 10.0})
        self.assertAlmostEqual(lat, 53.5, places=6)
        self.assertAlmostEqual(lng, -113.5, places=6)

    def test_the_closing_point_does_not_drag_the_centroid(self):
        """A GeoJSON ring repeats its first vertex; averaging the duplicate
        pulls the centre toward that corner."""
        from src import sun_shade
        ring = [[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0], [0.0, 0.0]]
        lat, lng = sun_shade.default_anchor(self._boundary(ring), {})
        self.assertAlmostEqual(lat, 1.0, places=9)
        self.assertAlmostEqual(lng, 1.0, places=9)

    def test_the_site_pin_is_the_fallback(self):
        from src import sun_shade
        self.assertEqual(
            sun_shade.default_anchor({"features": []},
                                     {"latitude": 53.5, "longitude": -113.5}),
            (53.5, -113.5))

    def test_nothing_to_centre_on_returns_none(self):
        from src import sun_shade
        self.assertIsNone(sun_shade.default_anchor({"features": []}, {}))
        self.assertIsNone(sun_shade.default_anchor(None, None))

    def test_a_degenerate_boundary_is_not_a_boundary(self):
        from src import sun_shade
        ring = [[0.0, 0.0], [1.0, 0.0], [0.0, 0.0]]     # two distinct points
        self.assertIsNone(sun_shade.default_anchor(self._boundary(ring), {}))

    def test_it_does_not_import_the_map_layer(self):
        """This module has to stay importable without Qt or the map — the
        suite skips ~156 widget tests on a bare container, and a rule that
        only runs where Qt runs is a rule that stops running."""
        src = (_SRC / "sun_shade.py").read_text(encoding="utf-8")
        self.assertNotIn("PyQt6", src)
        self.assertNotIn("map_widget", src)


# ── The merged panel ────────────────────────────────────────────────────────

@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestMergedPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def _panel(self):
        from src.analysis_panel import AnalysisPanel
        return AnalysisPanel()

    def test_one_date_drives_both_the_arc_and_the_shade(self):
        """The whole point of the merge: they cannot disagree because there is
        only one control to read."""
        panel = self._panel()
        panel._sun_date.setCurrentIndex(1)               # Winter Solstice
        panel._sun_time_slider.setValue(
            max(panel._sun_time_slider.minimum(), 13 * 60))
        cfg = panel._sun_config()
        month, day, hour, minute = panel._shade_when()
        self.assertEqual(cfg["date"][5:], f"{month:02d}-{day:02d}")
        self.assertEqual(hour * 60 + minute, panel._sun_time_slider.value())

    def test_showing_the_shade_asks_for_the_instant_on_screen(self):
        panel = self._panel()
        asked = []
        panel.shade_requested.connect(asked.append)
        panel._on_show_shade()
        self.assertEqual(asked[-1]["when"], panel._shade_when())
        self.assertNotIn("only_if_active", asked[-1])

    def test_a_scrub_never_conjures_a_shade_overlay(self):
        """The clock now belongs to both features. Dragging it to move the sun
        must not start a shade worker for an overlay nobody asked for."""
        panel = self._panel()
        asked = []
        panel.shade_requested.connect(asked.append)
        panel._emit_shade_for_scrub()
        self.assertTrue(asked[-1]["only_if_active"])

    def test_the_controller_honours_only_if_active(self):
        """AST-only: the guard has to come before anything is started, or the
        early return happens after a worker is already queued."""
        src = (_SRC / "controllers" / "map_events.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_on_shade_requested")
        guard = next((n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Constant) and n.value == "only_if_active"),
                     None)
        self.assertIsNotNone(guard, "the scrub guard is gone")
        work = [n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("_run_worker", "begin_shade_undo")]
        self.assertTrue(work)
        self.assertLess(guard, min(work))

    def test_scrubbing_moves_the_sun_at_once_and_the_shade_on_a_debounce(self):
        """Two update rates, deliberately: one moves a marker in JS over a
        cached payload, the other re-runs a grid pass on a worker thread."""
        panel = self._panel()
        sun, shade = [], []
        panel.sun_time_changed.connect(sun.append)
        panel.shade_requested.connect(shade.append)
        target = max(panel._sun_time_slider.minimum(),
                     min(panel._sun_time_slider.maximum(), 11 * 60))
        panel._sun_time_slider.setValue(target)
        self.assertIn(target, sun)
        self.assertEqual(shade, [], "the shade recompute was not debounced")
        self.assertTrue(panel._shade_scrub.isActive())

    def test_the_clock_spans_the_sites_real_daylight_before_anything_is_drawn(self):
        panel = self._panel()
        panel._sun_date.setCurrentIndex(1)               # Winter Solstice
        panel.set_site_location(53.55, -113.49)
        self.assertGreater(panel._sun_time_slider.minimum(), 8 * 60)
        self.assertLess(panel._sun_time_slider.maximum(), 17 * 60)

    def test_redating_keeps_the_hour_you_were_looking_at(self):
        panel = self._panel()
        panel.set_site_location(53.55, -113.49)
        panel._sun_date.setCurrentIndex(0)               # Summer Solstice
        panel._sun_time_slider.setValue(14 * 60)
        panel._sun_date.setCurrentIndex(2)               # Spring Equinox
        self.assertEqual(panel._sun_time_slider.value(), 14 * 60)

    def test_a_shorter_day_pulls_an_out_of_range_hour_back_in(self):
        panel = self._panel()
        panel.set_site_location(53.55, -113.49)
        panel._sun_date.setCurrentIndex(0)               # Summer Solstice
        panel._sun_time_slider.setValue(panel._sun_time_slider.maximum())
        panel._sun_date.setCurrentIndex(1)               # Winter Solstice
        self.assertLessEqual(panel._sun_time_slider.value(),
                             panel._sun_time_slider.maximum())
        self.assertGreaterEqual(panel._sun_time_slider.value(),
                                panel._sun_time_slider.minimum())

    def test_a_leaf_off_date_explains_its_thinner_shadows(self):
        panel = self._panel()
        panel._sun_date.setCurrentIndex(1)               # Dec 21 — bare crowns
        self.assertTrue(panel._shade_leafoff_note.isVisibleTo(panel))
        panel._sun_date.setCurrentIndex(0)               # Jun 21 — in leaf
        self.assertFalse(panel._shade_leafoff_note.isVisibleTo(panel))

    def test_showing_the_sun_path_does_not_demand_a_map_click(self):
        panel = self._panel()
        asked = []
        panel.sun_path_requested.connect(asked.append)
        panel._on_show_sun_path()
        self.assertFalse(asked[-1].get("pick_anchor"),
                         "the arc still requires the user to aim first")

    def test_move_is_still_available_for_the_case_that_needs_it(self):
        panel = self._panel()
        asked = []
        panel.sun_path_requested.connect(asked.append)
        panel._on_move_sun_path()
        self.assertTrue(asked[-1]["pick_anchor"])
        # Everything else about the request must be identical.
        self.assertEqual({k: v for k, v in asked[-1].items()
                          if k != "pick_anchor"}, panel._sun_config())

    def test_the_shade_controls_all_moved(self):
        """Each one must exist here, or the merge dropped a feature."""
        panel = self._panel()
        for name in ("_shade_opacity", "_shade_scrub", "_zones_show_cb",
                     "_shade_zone_status", "_shade_leafoff_note",
                     "_caster_summary"):
            self.assertTrue(hasattr(panel, name), name)
        for sig in ("shade_requested", "shade_cleared", "shade_opacity",
                    "shade_zones_requested", "shade_zones_visible_changed"):
            self.assertTrue(hasattr(panel, sig), sig)

    def test_the_caster_line_tracks_the_project(self):
        panel = self._panel()
        panel.update_caster_summary({"features": []})
        self.assertIn("No existing features", panel._caster_summary.text())
        panel.update_caster_summary(
            {"features": [{"properties": {"element_type": "existing_tree"}}]})
        self.assertIn("1 tree", panel._caster_summary.text())


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestSitePanelKeepsOnlyTheCapture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_the_shade_map_is_gone_from_the_site_panel(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        for gone in ("_shade_season", "_shade_hour", "_shade_opacity",
                     "_zones_show_cb", "_shade_scrub"):
            self.assertFalse(hasattr(panel, gone),
                             f"{gone} is still on the Site panel — two shade "
                             "controls is the bug this merge removed")
        for gone in ("shade_requested", "shade_cleared", "shade_opacity"):
            self.assertFalse(hasattr(panel, gone), gone)

    def test_but_the_caster_inventory_stays_where_they_are_entered(self):
        from src.site_panel import SitePanel
        panel = SitePanel()
        panel.update_caster_summary(
            {"features": [{"properties": {"element_type": "existing_building"}},
                          {"properties": {"element_type": "existing_tree"}}]})
        self.assertIn("1 building", panel._caster_summary.text())
        self.assertIn("1 tree", panel._caster_summary.text())


class TestWiring(unittest.TestCase):
    """AST/source guards — these run without Qt, which is the point."""

    def test_the_shade_signals_are_connected_from_the_analysis_panel(self):
        src = (_SRC / "app.py").read_text(encoding="utf-8")
        for sig in ("shade_requested", "shade_cleared", "shade_opacity",
                    "shade_zones_requested", "shade_zones_visible_changed"):
            self.assertIn(f"self.analysis_panel.{sig}.connect", src)
            self.assertNotIn(f"self.site_panel.{sig}.connect", src)

    def test_the_controller_reads_the_opacity_from_its_new_home(self):
        src = (_SRC / "controllers" / "map_events.py").read_text(encoding="utf-8")
        self.assertIn("analysis_panel._shade_opacity", src)
        self.assertNotIn("site_panel._shade_opacity", src)

    def test_the_zone_status_goes_to_the_panel_that_shows_it(self):
        src = (_SRC / "controllers" / "map_events.py").read_text(encoding="utf-8")
        self.assertNotIn("site_panel.set_shade_zone_status", src)
        self.assertNotIn("site_panel.mark_zones_shown", src)

    def test_the_arc_defaults_to_the_property(self):
        src = (_SRC / "controllers" / "map_events.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "_on_sun_path_requested")
        dump = ast.dump(fn)
        self.assertIn("default_anchor", dump)
        self.assertIn("pick_anchor", dump)
        self.assertIn("enter_sun_anchor_mode", dump)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestDrawingTheArcIsUndoable(unittest.TestCase):
    """The click path was ``@undoable``; the new default-anchor path has to be
    too, or pressing 'Show sun path' produces an arc Ctrl+Z cannot remove."""

    def test_both_paths_to_an_arc_are_undoable(self):
        src = (_SRC / "controllers" / "map_events.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for name in ("_on_sun_path_requested", "_on_sun_anchor_placed"):
            fn = next(n for n in ast.walk(tree)
                      if isinstance(n, ast.FunctionDef) and n.name == name)
            decorators = [ast.dump(d) for d in fn.decorator_list]
            self.assertTrue(any("undoable" in d for d in decorators),
                            f"{name} is not @undoable")


class TestTheWelcomeTimerSurvivesADeletedWindow(unittest.TestCase):
    """V2.38 — the welcome dialog is scheduled 150 ms after launch, and in that
    window the MainWindow can be gone.

    Rare in normal use (quit within a sixth of a second), routine in the test
    suite, which builds a probe window and deletes it immediately. Parenting a
    dialog to a deleted C++ object raises RuntimeError inside a Qt slot, and an
    exception escaping a Qt slot calls qFatal() — a process abort. On Windows
    that killed the whole test run before it could print its summary.
    """

    def test_the_deferred_welcome_checks_the_window_is_still_there(self):
        src = (_SRC / "onboarding_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef)
                   and n.name == "_welcome_if_alive"), None)
        self.assertIsNotNone(fn, "the guarded entry point is gone")
        dump = ast.dump(fn)
        self.assertIn("is_alive", dump)
        # The guard must come before the dialog is opened, or it guards nothing.
        guard = next(n.lineno for n in ast.walk(fn)
                     if isinstance(n, ast.Name) and n.id == "is_alive")
        opened = next(n.lineno for n in ast.walk(fn)
                      if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name)
                      and n.func.id == "show_welcome")
        self.assertLess(guard, opened)

    def test_the_timer_does_not_call_show_welcome_directly(self):
        """A bare lambda straight to show_welcome is the shape of the bug."""
        src = (_SRC / "onboarding_flow.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  and n.name == "maybe_show_welcome")
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "show_welcome"):
                self.fail("maybe_show_welcome schedules show_welcome without "
                          "the is_alive guard")

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_a_dead_window_is_a_no_op_rather_than_a_crash(self):
        from PyQt6.QtWidgets import QWidget
        _app = QApplication.instance() or QApplication([])
        from src.onboarding_flow import _welcome_if_alive
        w = QWidget()
        import PyQt6.sip as sip
        sip.delete(w)
        _welcome_if_alive(w)          # must simply return
        _welcome_if_alive(None)


class TestWorkersAreJoinedOnClose(unittest.TestCase):
    """A QThread destroyed while still running is qFatal() — a process abort.

    The window starts workers in ten places (terrain fetch, region download,
    shade, shade zones, generation, soil, buildings, wind, tree detection) and
    until V2.38 stopped none of them on close, so quitting mid-fetch aborted
    on the way out. It surfaced as a test suite dying after its final test with
    "QThread: Destroyed while thread '' is still running" — same event, seen
    from the other side.
    """

    def test_close_event_joins_them(self):
        src = (_SRC / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "closeEvent")
        self.assertIn("stop_threads", ast.dump(fn),
                      "closeEvent no longer joins its workers — quitting "
                      "mid-fetch will abort instead of exiting")

    def test_it_never_terminates_a_thread(self):
        """Killing a worker mid-statement can leave a SQLite write half
        applied. Corrupting the catalogue to make an exit tidy is a bad
        trade."""
        src = (_SRC / "qt_safety.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "stop_threads")
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "terminate"):
                self.fail("stop_threads calls terminate()")

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_a_running_worker_is_waited_for(self):
        from PyQt6.QtCore import QThread
        from PyQt6.QtWidgets import QWidget
        _app = QApplication.instance() or QApplication([])
        from src.qt_safety import stop_threads

        owner = QWidget()
        thread = QThread(owner)
        thread.start()
        self.assertTrue(thread.isRunning())
        self.assertEqual(stop_threads(owner, timeout_ms=5000), [])
        self.assertFalse(thread.isRunning(), "the worker was not joined")

    @unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
    def test_a_dead_owner_is_a_no_op(self):
        from PyQt6.QtWidgets import QWidget
        import PyQt6.sip as sip
        _app = QApplication.instance() or QApplication([])
        from src.qt_safety import stop_threads
        w = QWidget()
        sip.delete(w)
        self.assertEqual(stop_threads(w), [])
        self.assertEqual(stop_threads(None), [])
