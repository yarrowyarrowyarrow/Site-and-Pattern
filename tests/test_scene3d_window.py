"""
tests/test_scene3d_window.py — the 3D Preview window (V1.62).

Qt-gated smoke tests: the window constructs against a minimal fake main,
refresh() builds a Scene JSON from the live project and pushes it through
the viewer, the year slider re-pushes with the new year, and open_3d_view
keeps a singleton on the main. The viewer's run_js is overridden to
capture — no real page, no network, no DB (plants are resolved through
build_scene's get_plant default only if a plant feature exists; these
projects use existing-feature types to stay DB-free).
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
        return True
    except Exception:
        return False


def _scene_payloads(captured):
    """Parse the permaSetScene payload out of each captured JS push."""
    out = []
    for js in captured:
        if "permaSetScene(" not in js:
            continue
        start = js.index("(", js.index("permaSetScene(")) + 1
        out.append(json.loads(js[start:-2]))
    return out


@unittest.skipUnless(_qt_available(), "PyQt6/WebEngine not installed")
class TestScene3DWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _fake_main(self):
        class _Fake:
            pass
        m = _Fake()
        # No boundary and no site pin → the terrain worker is never started.
        m._project = {
            "type": "FeatureCollection",
            "properties": {"site_config": {}},
            "features": [
                {"type": "Feature",
                 "geometry": {"type": "Point",
                              "coordinates": [-113.5, 53.5]},
                 "properties": {"element_type": "existing_tree",
                                "height_m": 9.0, "canopy_radius_m": 3.0}},
            ],
        }
        return m

    def test_refresh_pushes_scene_from_project(self):
        from src.scene3d_window import Scene3DWindow
        win = Scene3DWindow(self._fake_main())
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        win.refresh()
        scenes = _scene_payloads(captured)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["version"], 1)
        self.assertEqual(len(scenes[0]["plants"]), 1)
        self.assertTrue(scenes[0]["plants"][0]["existing"])
        self.assertIsNone(win._thread)   # no boundary/pin → no fetch
        win.close()          # closeEvent stops its workers
        win.deleteLater()

    def test_year_slider_repushes_scene(self):
        from src.scene3d_window import Scene3DWindow
        win = Scene3DWindow(self._fake_main())
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        win._year.setValue(10)
        scenes = _scene_payloads(captured)
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["year"], 10)
        self.assertEqual(win._year_lbl.text(), "year 10")
        win.close()          # closeEvent stops its workers
        win.deleteLater()

    def test_the_time_sliders_have_room_on_a_laptop(self):
        """V3.05: at the 1148 px the window opens at on a 1366 x 768 screen,
        Year, Time of year and Time of day were 15 px wide, a handle that read
        as a checkbox, because their row also held six buttons (the surface
        audit measured it). Their row now holds only when and how it looks.
        They are the Advanced tools' since V3.44, so the switch is on here."""
        from src.scene3d_window import Scene3DWindow
        win = Scene3DWindow(self._fake_main())
        win.viewer.run_js = lambda js: None
        win.set_advanced_tools(True)
        win.resize(1148, 700)
        win.show()
        for _ in range(5):
            self._app.processEvents()
        for slider in (win._year, win._month, win._hour):
            self.assertTrue(slider.isVisible())
            self.assertGreaterEqual(slider.width(), 100)
        win.close()
        win.deleteLater()

    # ── V3.44 (F261): a window a homeowner can use ──────────────────────────

    def _window(self, main=None):
        from src.scene3d_window import Scene3DWindow
        win = Scene3DWindow(main or self._fake_main())
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        self.addCleanup(win.deleteLater)
        self.addCleanup(win.close)
        return win, captured

    def _shown(self, win):
        win.resize(960, 700)
        win.show()
        for _ in range(5):
            self._app.processEvents()

    def _yard_main(self):
        """A fake main whose design has an outline, so it has a street."""
        main = self._fake_main()
        d = 0.0002
        ring = [[-113.5 - d, 53.5 - d], [-113.5 + d, 53.5 - d],
                [-113.5 + d, 53.5 + d], [-113.5 - d, 53.5 + d]]
        main._project["features"].append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]},
            "properties": {"element_type": "property_boundary"}})
        return main

    def test_it_opens_on_the_fifth_summer_in_july_from_the_street(self):
        """The owner's D5. It opened fully grown, in June, at one o'clock,
        from above: a picture no yard is ever in."""
        from src import scene3d_stops as stops
        win, captured = self._window(self._yard_main())
        win.refresh()
        scene = _scene_payloads(captured)[0]
        self.assertEqual((scene["year"], scene["month"]), (5, 7))
        self.assertEqual(win._hour.value(), 15)
        said = [box.currentText() for box, _e in win.when_bar._lists.values()]
        self.assertEqual(said, ["Fifth summer", "Summer", "Afternoon"])
        views = [js for js in captured if "permaShowView" in js]
        self.assertEqual(views, ['window.permaShowView && '
                                 'window.permaShowView("street");'])
        self.assertLess(captured.index(next(js for js in captured
                                            if "permaSetScene" in js)),
                        captured.index(views[0]),
                        "the view must land after the scene it looks at")
        self.assertEqual(stops.OPENING["view"], "street")

    def test_the_opening_view_is_shown_once_a_design(self):
        """A slider moving, or an edit, leaves the camera where the person
        put it; another design gets the opening view again."""
        main = self._yard_main()
        win, captured = self._window(main)
        win.refresh()
        win._month.setValue(9)
        win.follow_design()
        self.assertEqual(len([j for j in captured if "permaShowView" in j]), 1)
        main._project = {
            "type": "FeatureCollection",
            "properties": {"site_config": {"latitude": 51.0,
                                           "longitude": -110.0}},
            "features": [{"type": "Feature", "geometry": {
                "type": "Point", "coordinates": [-110.0, 51.0]},
                "properties": {"element_type": "existing_tree",
                               "height_m": 9.0, "canopy_radius_m": 3.0}}]}
        win.follow_design()
        self.assertEqual(len([j for j in captured if "permaShowView" in j]), 2)

    def test_a_design_with_no_yard_opens_on_the_whole_of_it(self):
        """No outline and nothing planted: there is no street to stand on, and
        the opening view is the whole stage, as it always was. And where the
        house hides the planting from the street, it opens from the house
        (``scene_views.opening_view``)."""
        from unittest import mock
        win, captured = self._window()
        win.refresh()
        self.assertEqual([j for j in captured if "permaShowView" in j],
                         ['window.permaShowView && '
                          'window.permaShowView("whole");'])
        del captured[:]
        win._shown_origin = None
        with mock.patch("src.scene_views.opening_view", lambda _v: "house"):
            win._push_scene()
        self.assertIn('permaShowView("house")', "".join(captured))

    def test_it_does_not_take_the_camera_from_a_walk(self):
        win, captured = self._window()
        win._walk_btn.setChecked(True)
        win.refresh()
        self.assertEqual([j for j in captured if "permaShowView" in j], [])

    def test_the_simple_window_is_two_short_rows(self):
        """Finding 13: sixteen controls in three rows, a quarter of them the
        pollinator tools. A homeowner sees three lists and five buttons, each
        with its name on it, and the window is not forced wide."""
        from PyQt6.QtWidgets import QComboBox, QPushButton, QSlider
        win, _captured = self._window()
        self._shown(win)
        self.assertFalse(win.advanced_rows.isVisible())
        seen = [w for w in win.findChildren((QComboBox, QPushButton, QSlider))
                if w.isVisible()]
        names = [w.accessibleName() or w.text() for w in seen]
        self.assertEqual(names, ["When", "Season", "Time of day",
                                 "From the street", "From the house",
                                 "From above", "Walk", "Reset view"])
        self.assertTrue(all(names), "a control with no name")
        self.assertLessEqual(win.minimumSizeHint().width(), 960)
        for w, name in zip(seen, names):
            self.assertGreaterEqual(w.height(), 24, name)

    def test_advanced_tools_bring_the_rest_back(self):
        from PyQt6.QtWidgets import QPushButton
        win, _captured = self._window()
        self._shown(win)
        win.set_advanced_tools(True)
        self._app.processEvents()
        self.assertTrue(win.advanced_rows.isVisible())
        for w in (win._year, win._month, win._hour, win._detail, win._fly_btn,
                  win._id_btn, win._bee_btn, win._bee_combo, win._tour_btn,
                  win._spot_btn, win._plant_btn, win._pull_btn,
                  win._still_btn, win._ba_btn):
            self.assertTrue(w.isVisible(), w)
        walks = [b for b in win.findChildren(QPushButton)
                 if "Walk" in b.text()]
        self.assertEqual(len(walks), 1, "one Walk button, in the View row")
        resets = [b for b in win.findChildren(QPushButton)
                  if "Reset" in b.text()]
        self.assertEqual(len(resets), 1)

    def test_a_new_window_reads_the_switch(self):
        from unittest import mock
        from src import advanced_tools
        with mock.patch.object(advanced_tools, "is_on", lambda *_a: True):
            win, _captured = self._window()
            self._shown(win)
            self.assertTrue(win.advanced_rows.isVisible())

    def test_switching_off_stops_what_it_hides(self):
        """As the switch cancels Measure on the map: nothing is left running
        with no button to stop it."""
        from src import scene3d_edit_flow as edit_flow
        win, captured = self._window()
        win.set_advanced_tools(True)
        win._id_btn.setChecked(True)
        win._spot_btn.setChecked(True)
        win._fly_btn.setChecked(True)
        win._plant_btn.setChecked(True)
        edit_flow.set_mode(win, "plant")
        del captured[:]
        win.set_advanced_tools(False)
        for btn in (win._id_btn, win._spot_btn, win._fly_btn, win._plant_btn):
            self.assertFalse(btn.isChecked(), btn.text())
        sent = "".join(captured)
        self.assertIn("permaSetWildlifeLabels(false)", sent)
        self.assertIn("permaSetCinematic(false)", sent)
        self.assertIn('permaSetEditMode("", null)', sent)
        self.assertIsNotNone(win._fly_timer)
        self.assertFalse(win._fly_timer.isActive())

    def test_the_trowel_says_which_year_it_plants_in(self):
        """The year on the slider is the year a plant goes in (V2.44), and the
        window opens on the fifth summer now: a plant put in from there is
        five years behind the rest, so the hint says so and follows the year."""
        from unittest import mock
        from src import scene3d_edit_flow as edit_flow
        win, _captured = self._window()
        win.set_advanced_tools(True)
        pick = {"plant_id": 3, "common_name": "Wild Bergamot"}
        with mock.patch.object(win, "_current_plant_pick", lambda: pick):
            win._plant_btn.setChecked(True)
            edit_flow.set_mode(win, "plant")
            self.assertEqual(win._edit_hint.text(),
                             "Planting Wild Bergamot in the fifth summer.")
            win._year.setValue(1)
            self.assertEqual(win._edit_hint.text(),
                             "Planting Wild Bergamot in the first summer.")
            win._push_timer.stop()
            win._year.setValue(0)
            self.assertEqual(win._edit_hint.text(), "Planting Wild Bergamot.")
        with mock.patch.object(win, "_current_plant_pick", lambda: None):
            win._push_timer.stop()
            win._year.setValue(2)
            self.assertIn("first", win._edit_hint.text())     # pick one first

    def test_the_lists_and_the_sliders_say_the_same_thing(self):
        win, captured = self._window()
        box = win.when_bar._lists["year"][0]
        box.setCurrentIndex(box.findText("Tenth summer"))
        win.when_bar._on_list("year")
        self.assertEqual(win._year.value(), 10)
        self.assertEqual(_scene_payloads(captured)[-1]["year"], 10)
        win._push_timer.stop()
        win._year.setValue(7)                  # the fine slider, off a stop
        self.assertEqual(box.currentText(), "Seventh summer")
        self.assertEqual(win._year_lbl.text(), "year 7")
        win._push_timer.stop()
        win._year.setValue(0)
        self.assertEqual(box.currentText(), "Fully grown")
        self.assertEqual(box.count(), 6, "the off-stop entry went with it")
        season = win.when_bar._lists["month"][0]
        season.setCurrentIndex(season.findText("Winter"))
        win.when_bar._on_list("month")
        self.assertEqual(win._month.value(), 1)

    def test_a_drag_is_one_push_an_interval(self):
        """Finding 14: every slider tick was a full rebuild, 25 for a drag of
        Year. The first move pushes at once; the rest of the interval's moves
        are one push, of the value the slider ends on."""
        win, captured = self._window()
        win._year.setValue(10)
        self.assertEqual(len(_scene_payloads(captured)), 1)
        for year in (11, 12, 13, 14, 15):
            win._year.setValue(year)
        self.assertEqual(len(_scene_payloads(captured)), 1)
        self.assertEqual(win._year_lbl.text(), "year 15",
                         "the label follows at once")
        win._on_push_interval()                # the interval ends
        scenes = _scene_payloads(captured)
        self.assertEqual([sc["year"] for sc in scenes], [10, 15])
        win._on_push_interval()                # nothing waiting: nothing sent
        self.assertEqual(len(_scene_payloads(captured)), 2)

    def test_a_named_view_leaves_the_walk_first(self):
        win, captured = self._window()
        win.refresh()
        del captured[:]
        win.view_bar._walk_btn.click()
        win.view_bar.view_buttons["above"].click()
        self.assertFalse(win._walk_btn.isChecked())
        import re
        order = [re.search(r"&& window\.(perma\w+\(.*\));$", js).group(1)
                 for js in captured if "WalkMode" in js or "ShowView" in js]
        self.assertEqual(order, ["permaSetWalkMode(true)",
                                 "permaSetWalkMode(false)",
                                 'permaShowView("above")'])

    def test_from_the_house_says_what_it_needs(self):
        """No building in the outline: the button is off and says why, as a
        switch with nothing to change does (V3.19)."""
        from src import scene3d_stops as stops
        win, _captured = self._window()
        win.refresh()
        house = win.view_bar.view_buttons["house"]
        self.assertFalse(house.isEnabled())
        self.assertEqual(house.toolTip(), stops.NO_HOUSE)
        self.assertTrue(win.view_bar.view_buttons["street"].isEnabled())

    def test_the_shade_simulation_is_kept_between_pushes(self):
        from unittest import mock
        import src.scene3d_window as mod
        win, _captured = self._window()
        memos = []
        real = mod.build_scene

        def spy(project, **kw):
            memos.append(kw.get("memo"))
            return real(project, **kw)
        with mock.patch.object(mod, "build_scene", spy):
            win.refresh()
            win._push_scene()
        self.assertIs(memos[0], win._memo)
        self.assertIs(memos[1], win._memo)

    def test_the_pollinator_it_starts_on_has_an_english_name(self):
        """It opened on *Agapostemon femoratus*: first by genus, Latin only,
        on a design that might hold nothing it uses. The rule is tested in
        ``test_scene3d_creatures``; this is the window obeying it, and leaving
        the person's own choice alone."""
        from unittest import mock
        from tests.test_scene3d_creatures import ROWS
        with mock.patch("src.scene3d_creatures.rows", lambda: list(ROWS)):
            win, _captured = self._window()
        self.assertEqual(win._current_creature()["name"],
                         "Half-black Bumble Bee")
        fed = lambda _rows, _ids, **_k: 5                      # noqa: E731
        with mock.patch("src.scene3d_creatures.default_row", fed):
            win.refresh()
        self.assertEqual(win._current_creature()["name"],
                         "Tricoloured Bumble Bee",
                         "the one this design feeds, once there is a design")
        win._bee_combo.setCurrentIndex(4)
        win._bee_combo.activated.emit(4)                 # the person chose
        win._shown_origin = None                         # another design
        with mock.patch("src.scene3d_creatures.default_row", fed):
            win._push_scene()
        self.assertEqual(win._current_creature()["name"],
                         "Half-black Bumble Bee")

    def test_it_follows_the_design_in_the_apps_colours(self):
        """F89: no Refresh from design, the window rebuilds when the design
        changes (src/follow_design.py); F209: dark like the app."""
        from PyQt6.QtWidgets import QPushButton
        from src.scene3d_window import Scene3DWindow
        from src.ui_style import WINDOW_STYLE
        main = self._fake_main()
        win = Scene3DWindow(main)
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        words = [b.text() for b in win.findChildren(QPushButton)]
        self.assertFalse([w for w in words if "Refresh" in w], words)
        self.assertEqual(win.styleSheet(), WINDOW_STYLE)
        tree = dict(main._project["features"][0])
        tree["geometry"] = {"type": "Point", "coordinates": [-113.5001, 53.5]}
        main._project["features"].append(tree)
        win.follow_design()
        self.assertEqual(len(_scene_payloads(captured)[-1]["plants"]), 2)
        win.close()
        win.deleteLater()

    def test_open_3d_view_singleton(self):
        from src.scene3d_window import open_3d_view
        main = self._fake_main()
        w1 = open_3d_view(main)
        w2 = open_3d_view(main)
        self.assertIs(w1, w2)
        self.assertIs(main._scene3d_window, w1)
        w1.close()
        w1.deleteLater()

    def test_opening_it_again_keeps_the_camera_unless_a_view_is_asked(self):
        """The plan strip's door raises the window and leaves the camera where
        the person put it; the Overview's street item asks for the street."""
        from src.scene3d_window import open_3d_view
        main = self._fake_main()
        win = open_3d_view(main)
        captured = []
        win.viewer.run_js = lambda js: captured.append(js)
        open_3d_view(main)
        self.assertEqual([j for j in captured if "permaShowView" in j], [])
        open_3d_view(main, "street")
        self.assertEqual(len([j for j in captured if "permaShowView" in j]), 1)
        win.close()
        win.deleteLater()

    def test_the_switch_reaches_a_window_that_is_open(self):
        """``advanced_tools.ADVANCED_HOOKS`` names a holder the main window
        always has: the 3D window does not exist until it is opened."""
        from src.scene3d_window import open_3d_view, tools_hook
        main = self._fake_main()
        hook = tools_hook(main)
        hook.set_advanced_tools(True)            # no window yet: nothing to do
        win = open_3d_view(main)
        win.viewer.run_js = lambda js: None
        self.assertFalse(win.advanced_rows.isVisible())
        hook.set_advanced_tools(True)
        self.assertTrue(win.advanced_rows.isVisible())
        hook.set_advanced_tools(False)
        self.assertFalse(win.advanced_rows.isVisible())
        win.close()
        win.deleteLater()


if __name__ == "__main__":
    unittest.main()
