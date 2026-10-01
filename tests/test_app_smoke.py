"""
tests/test_app_smoke.py

Headless-Qt smoke test for src/app.py:MainWindow. The point is to give the
upcoming MainWindow decomposition (Chunk 5 of the strengthening roadmap)
a safety net — once the controllers are extracted, the public surface
that this test exercises must keep working.

The tests skip cleanly when PyQt6 is not importable in the current env
(e.g. CI without Qt), and also when MainWindow construction fails for
environmental reasons (QWebEngineView is fussy under some headless GL
stacks). On a dev machine with PyQt6 + Qt WebEngine installed they run
end-to-end. Run from project root::

    QT_QPA_PLATFORM=offscreen python -m unittest tests.test_app_smoke -v

This is a structural smoke test, not a behavioural one — it pins the
*existence* of the undo/redo stack, mode helpers, and project save/load
plumbing so a rename or accidental deletion fails loudly.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force offscreen platform BEFORE importing anything Qt-touching.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Sandbox the DB and config so the test never touches the real user data.
_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_app_smoke_")
_DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
_CFG_PATH = os.path.join(_TMP_DIR, "config.json")

try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = _DB_PATH
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = _CFG_PATH
except Exception:  # pragma: no cover — defensive, almost never trips
    pass


def _qt_available():
    try:
        import PyQt6  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestMainWindowSmoke(unittest.TestCase):
    """Construct a MainWindow once for the class, then exercise public state."""

    _app = None
    _win = None
    _construct_error: Exception | None = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])
        try:
            from src.app import MainWindow
            cls._win = MainWindow()
        except Exception as exc:  # noqa: BLE001 — capture for skipTest
            cls._construct_error = exc

    @classmethod
    def tearDownClass(cls):
        if cls._win is not None:
            cls._win.close()
            cls._win.deleteLater()
            cls._win = None

    def setUp(self):
        if self._construct_error is not None:
            self.skipTest(
                f"MainWindow construction failed in this env: "
                f"{type(self._construct_error).__name__}: {self._construct_error}"
            )

    # ── Basic class shape ────────────────────────────────────────────────────

    def test_constructed(self):
        self.assertIsNotNone(self._win)
        # Against branding.APP_TITLE (what app.py sets), not a literal: the
        # old literal went stale at the V1.69 rebrand and nobody noticed
        # because this module only runs on a full Qt stack (CI skips it).
        from src.branding import APP_TITLE
        self.assertEqual(self._win.windowTitle(), APP_TITLE)

    def test_initial_project_state(self):
        self.assertEqual(self._win._project["type"], "FeatureCollection")
        self.assertEqual(self._win._project["features"], [])
        self.assertIsNone(self._win._project_path)
        self.assertFalse(self._win._modified)
        self.assertEqual(self._win._current_mode, "none")

    def test_initial_undo_redo_state(self):
        self.assertEqual(self._win._undo_stack, [])
        self.assertEqual(self._win._redo_stack, [])

    # ── Undo/redo stack mechanics ────────────────────────────────────────────
    # `_push_undo` is the single entry point that all map-side mutations
    # funnel through; if Chunk 5 moves it to a controller, this guards the
    # invariant that pushing clears redo and the stack stays bounded.

    def test_push_undo_clears_redo(self):
        self._win._redo_stack = [{"action": "stale", "data": {}}]
        self._win._push_undo({"action": "test", "data": {"x": 1}})
        self.assertEqual(self._win._undo_stack[-1]["action"], "test")
        self.assertEqual(self._win._redo_stack, [])

    def test_push_undo_caps_stack_size(self):
        self._win._undo_stack = []
        cap = self._win._max_undo
        for i in range(cap + 5):
            self._win._push_undo({"action": "noop", "data": {"i": i}})
        self.assertEqual(len(self._win._undo_stack), cap)
        # Newest entry survives, oldest were dropped.
        self.assertEqual(self._win._undo_stack[-1]["data"]["i"], cap + 4)

    # ── Mode helpers ─────────────────────────────────────────────────────────

    def test_set_mode_label_updates_state(self):
        # `_set_mode_label` is what every _enter_*_mode helper calls; if a
        # mode name silently drifts, this catches it. The label widget
        # (`_sb_mode`, status-bar mode indicator) should reflect the new
        # text after the call.
        self._win._set_mode_label("BoundaryProbe")
        self.assertTrue(hasattr(self._win, "_sb_mode"))
        self.assertEqual(self._win._sb_mode.text(), "Mode: BoundaryProbe")

    def test_required_mode_methods_exist(self):
        for name in (
            "_enter_boundary_mode", "_enter_measure_mode",
            "_enter_annotate_mode", "_enter_plant_mode",
            "_enter_structure_mode", "_enter_hedgerow_mode",
            "_enter_shape_mode", "_set_mode_label",
            "_cancel_draw",
        ):
            self.assertTrue(
                callable(getattr(self._win, name, None)),
                f"MainWindow.{name} should remain reachable after Chunk 5",
            )

    # ── Persistence surface ──────────────────────────────────────────────────

    def test_required_persistence_methods_exist(self):
        for name in ("_on_save", "_on_save_as", "_do_undo", "_do_redo",
                     "_push_undo", "_autosave", "_start_autosave",
                     "_mark_modified"):
            self.assertTrue(
                callable(getattr(self._win, name, None)),
                f"MainWindow.{name} should remain reachable after Chunk 5",
            )

    # ── Update-flow surface ──────────────────────────────────────────────────

    def test_required_update_flow_methods_exist(self):
        # V2.22 deleted the git-mutation flows; V2.25 restored a one-click
        # updater by user request — but as controller methods
        # (UpdateFlowController._perform_source_update) over Qt-free helpers
        # (version_branch.update_to_branch), not as MainWindow shims. Only
        # the long-standing MainWindow surface is pinned here.
        for name in (
            "_on_check_for_updates",
            "_newest_remote_version_branch", "_is_newer_version",
            "_open_releases_page",
        ):
            self.assertTrue(
                callable(getattr(self._win, name, None)),
                f"MainWindow.{name} should remain reachable after Chunk 5",
            )

    def test_git_mutation_flows_removed(self):
        # The V1.x git working-tree manager's MainWindow shims stay dead.
        # The V2.25 one-click updater lives on UpdateFlowController with new
        # names; MainWindow itself never grew the surface back. (The
        # destructive reset---hard path is pinned out separately in
        # tests/test_architecture_guard.py.)
        for name in ("_run_update_flow", "_maybe_restore_stash",
                     "_offer_branch_switch"):
            self.assertFalse(
                hasattr(self._win, name),
                f"MainWindow.{name} was deleted in V2.22 — the one-click "
                f"updater belongs on UpdateFlowController, not MainWindow.",
            )

    # ── Legacy plant-API surface is gone ─────────────────────────────────────

    def test_legacy_api_helpers_removed(self):
        for name in ("_load_api_keys", "_on_settings"):
            self.assertFalse(
                hasattr(self._win, name),
                f"MainWindow.{name} should have been removed in Chunk 1",
            )

    # ── Generate-Design wiring (V1.44) ───────────────────────────────────────

    def test_generate_design_wiring_present(self):
        # The one-click entry point, its QAction, and the controller must exist.
        self.assertTrue(callable(getattr(self._win, "_on_generate_design", None)))
        self.assertTrue(hasattr(self._win, "_act_generate"))
        self.assertIsNotNone(getattr(self._win, "_generation", None))

    # ── The placement bar (F193, V2.98) ──────────────────────────────────────

    def test_placement_bar_sits_beside_the_map_not_inside_it(self):
        """A child of the web view never reaches the accessibility tree."""
        bar = self._win.placement_bar
        self.assertIs(bar.parentWidget(), self._win.map_widget.parentWidget())
        self.assertFalse(self._win.map_widget.isAncestorOf(bar))

    def test_the_map_bridge_lives_as_long_as_the_view(self):
        """The web channel keeps a bare pointer to the bridge. Owned only by a
        Python attribute, it was freed under a live page (CI, V2.98)."""
        from PyQt6 import sip
        bridge = self._win.map_widget.bridge
        self.assertIs(bridge.parent(), self._win.map_widget)
        self.assertFalse(sip.ispyowned(bridge))

    def test_looking_at_a_plant_leaves_the_map_alone(self):
        """V2.99 (F191): selecting names the plant on the Place button; only a
        Place action arms the map. Through the real window's wiring."""
        win = self._win
        panel = win.plant_panel
        win._cancel_draw()
        panel._results_list.setCurrentIndex(
            panel._results_list.model().index(0, 0))
        self.assertEqual(win._current_mode, "none")
        self.assertEqual(win.placement_bar.source, "")
        panel._place_btn.click()
        self.assertEqual(win._current_mode, "plant")
        self.assertEqual(win.placement_bar.source, "plants")
        win._cancel_draw()

    def test_choosing_a_plant_shows_its_page_and_placing_puts_it_away(self):
        """V3.00 (F192), through the real window: the page opens over the
        map's right edge, its Place arms the map, and placing closes it so the
        yard is clear for the click."""
        win = self._win
        panel = win.plant_panel
        fly = win.species_flyout
        win._cancel_draw()
        from src.plant_list_view import _PLANT_OBJ_ROLE
        index = panel._results_list.model().index(1, 0)
        plant = index.data(_PLANT_OBJ_ROLE)
        panel._on_list_choose(index)
        self.assertFalse(fly.isHidden())
        self.assertIs(fly.parentWidget(), win.map_widget.parentWidget())
        self.assertEqual(fly.page.shown_id(), plant["id"])
        self.assertEqual(win._current_mode, "none")
        fly.page.findChild(type(panel._place_btn), "placeButton").click()
        self.assertEqual(win._current_mode, "plant")
        self.assertEqual(win.placement_bar.source, "plants")
        self.assertTrue(fly.isHidden())
        self.assertEqual(panel._armed_plant["id"], plant["id"])
        win._cancel_draw()

    def test_closing_the_page_hands_the_keyboard_back_to_the_list(self):
        win = self._win
        panel = win.plant_panel
        fly = win.species_flyout
        win._cancel_draw()
        panel._on_list_read(panel._results_list.model().index(2, 0))
        self.assertFalse(fly.isHidden())
        fly.page.close_requested.emit()
        self.assertTrue(fly.isHidden())
        self.assertEqual(panel.page_plant_id(), 0)

    def test_the_list_knows_where_the_site_is(self):
        """For "Recorded near this site": read from the site panel, not pushed, so a
        loaded project's pin counts too."""
        panel = self._win.plant_panel
        self.assertEqual(panel._site_source,
                         self._win.site_panel.current_coords)

    def test_a_sites_soil_ph_shows_as_a_filter_you_can_remove(self):
        """V1.67 made a fetched soil's pH filter Browse and nothing said so;
        at pH 8.0 it hides a quarter of the catalogue (V3.01)."""
        from src import soil_flow
        picker = self._win.plant_panel.picker
        every = len(picker.rows())
        sc = (self._win._project.setdefault("properties", {})
              .setdefault("site_config", {}))
        before = dict(sc)
        self.addCleanup(lambda: (sc.clear(), sc.update(before)))
        self.addCleanup(lambda: self._win.plant_panel.set_soil_ph(None))
        soil_flow.apply_soil_site_fields(
            self._win, {"summary": {"ph_top": 8.0}})
        self.assertIn("Your soil: pH 8.0", picker.chip_texts())
        self.assertLess(len(picker.rows()), every)
        picker.remove("soil")
        self.assertNotIn("Your soil: pH 8.0", picker.chip_texts())
        self.assertEqual(len(picker.rows()), every)
        picker.set_soil_on(True)

    def _leave_the_window_as_found(self):
        """The window is shared by the class. A test that changes the design
        puts back its title (test_constructed reads it), its path, its undo
        stack and its changed-flag: closing a changed window asks first, a
        modal nobody answers in a test."""
        self.addCleanup(self._win.setWindowTitle, self._win.windowTitle())
        self.addCleanup(setattr, self._win, "_project_path", None)
        self.addCleanup(setattr, self._win, "_modified", False)
        self.addCleanup(self._win._clear_undo)

    def test_a_pin_taken_away_takes_its_soil_filter(self):
        """Removing the pin dropped its soil data but went on filtering Browse
        by its pH, and kept `soil_ph` in the saved design (V3.01)."""
        from src import soil_flow
        picker = self._win.plant_panel.picker
        sc = (self._win._project.setdefault("properties", {})
              .setdefault("site_config", {}))
        before = dict(sc)
        self.addCleanup(lambda: (sc.clear(), sc.update(before)))
        self._leave_the_window_as_found()
        soil_flow.apply_soil_site_fields(
            self._win, {"summary": {"ph_top": 8.0}})
        self.assertEqual(picker.soil_ph(), 8.0)
        self._win._map_events._on_site_pin_removed()
        self.assertIsNone(picker.soil_ph())
        self.assertNotIn("soil_ph", sc)
        self.assertFalse(any("Your soil" in c for c in picker.chip_texts()))

    def test_a_design_with_no_pin_has_no_soil_filter(self):
        """A new design, or one opened without a pin, kept the last design's
        soil pH until V3.01, under a chip that now says "Your soil"."""
        from unittest import mock
        from src import project as project_io, soil_flow
        picker = self._win.plant_panel.picker
        self._leave_the_window_as_found()
        for opened in ("new", "loaded"):
            soil_flow.apply_soil_site_fields(
                self._win, {"summary": {"ph_top": 8.0}})
            self.assertEqual(picker.soil_ph(), 8.0, opened)
            self._win._modified = False
            if opened == "new":
                with mock.patch("src.app.QInputDialog.getText",
                                return_value=("Soil test", True)):
                    self._win._on_new()
            else:
                path = os.path.join(tempfile.mkdtemp(), "no-pin.perma.geojson")
                project_io.save_project(project_io.new_project("No pin"), path)
                # Loading remembers the design in the user's settings.
                with mock.patch("src.saves.remember_last_design"):
                    self._win._load_from_path(path)
            self.assertIsNone(picker.soil_ph(), opened)
            self.assertFalse(any("Your soil" in c
                                 for c in picker.chip_texts()), opened)

    # ── The accessibility baseline (F195, V3.02) ──────────────────────────

    def test_every_control_has_a_name_a_screen_reader_can_read(self):
        """Shown or not: a control that appears only in one state is still
        read in it. A name is an accessible name, the control's own text, or
        a label pointing at it; a group box's title and a dropdown's current
        value are not, since they name the group and the choice. A button
        whose text arrives with its content says so (``namedByContent``: the
        quiz's answers, the Site tab's community link); any other button with
        no text needs a name, hidden or not, since a colour swatch in a closed
        form is still read once it opens."""
        from PyQt6.QtWidgets import (
            QAbstractButton, QAbstractItemView, QAbstractSlider,
            QAbstractSpinBox, QComboBox, QLabel, QLineEdit, QMenuBar,
            QScrollBar, QTabBar, QTextEdit, QWidget,
        )
        controls = (QAbstractButton, QComboBox, QLineEdit, QAbstractSlider,
                    QAbstractSpinBox, QAbstractItemView, QTextEdit)
        parts = (QComboBox, QAbstractSpinBox, QTabBar, QLineEdit,
                 QAbstractItemView, QMenuBar)

        def part_of_another(w):
            p = w.parentWidget()
            while p is not None:
                if isinstance(p, parts):
                    return True
                p = p.parentWidget()
            return False

        labelled = {id(lab.buddy()) for lab in self._win.findChildren(QLabel)
                    if lab.buddy() is not None}
        missing = []
        for w in self._win.findChildren(QWidget):
            if (not isinstance(w, controls) or isinstance(w, (QScrollBar, QTabBar))
                    or part_of_another(w) or w.objectName().startswith("qt_")
                    or w.window() is not self._win):
                continue
            if w.accessibleName().strip() or id(w) in labelled:
                continue
            if isinstance(w, QAbstractButton) and (
                    w.text().strip() or w.property("namedByContent")):
                continue
            hint = (getattr(w, "placeholderText", lambda: "")() or w.toolTip()
                    or "")[:40]
            missing.append(f"{type(w).__name__} {hint!r}")
        self.assertEqual(missing, [], "controls a screen reader cannot name")

    def _focus_on(self, widget):
        self._win.show()
        self._win.activateWindow()
        widget.setFocus()
        self._app.processEvents()
        if self._app.focusWidget() is not widget:
            self.skipTest("this platform does not give the window focus")

    def _press(self, key):
        from PyQt6.QtCore import QEvent, Qt
        from PyQt6.QtGui import QKeyEvent
        self._win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key,
                                          Qt.KeyboardModifier.NoModifier))

    def test_single_letters_wait_for_the_map(self):
        """With focus on a side-panel button, B started a boundary and A
        switched tabs (measured on V3.01); Delete removed the map's selection."""
        from unittest import mock
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QPushButton
        self.addCleanup(self._win._cancel_draw)
        button = next(b for b in self._win.polyculture_panel.findChildren(QPushButton)
                      if b.text() == "New Community")
        from src import keyboard_help
        keyboard_help.show_panel(self._win.polyculture_panel)
        self._focus_on(button)
        tab = self._win._side_tabs.currentIndex()
        self._press(Qt.Key.Key_B)
        self._press(Qt.Key.Key_A)
        self.assertEqual(self._win._current_mode, "none")
        self.assertEqual(self._win._side_tabs.currentIndex(), tab)
        with mock.patch.object(self._win.map_widget, "delete_selected") as delete:
            self._press(Qt.Key.Key_Delete)
        delete.assert_not_called()

    def test_on_the_map_the_letters_act(self):
        from unittest import mock
        from PyQt6.QtCore import Qt
        from src import keyboard_help
        self.addCleanup(self._win._cancel_draw)
        with mock.patch.object(keyboard_help, "map_has_focus", return_value=True):
            self._press(Qt.Key.Key_G)
            self.assertTrue(self._win.polyculture_panel.isVisibleTo(self._win))
            self._press(Qt.Key.Key_P)
            self.assertTrue(self._win.plant_panel.isVisibleTo(self._win))
            self._press(Qt.Key.Key_B)
            self.assertEqual(self._win._current_mode, "boundary")
            with mock.patch.object(self._win.map_widget,
                                   "delete_selected") as delete:
                self._press(Qt.Key.Key_Delete)
            delete.assert_called_once()

    def test_every_tool_and_view_toggle_is_reached_by_tab(self):
        """A QToolBar makes its buttons NoFocus: no tool and no View toggle
        could be reached from the keyboard. TabFocus, so a click on a tool
        leaves focus on the map."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QToolBar, QToolButton
        buttons = [b for bar in self._win.findChildren(QToolBar)
                   for b in bar.findChildren(QToolButton)
                   if not b.objectName().startswith("qt_")]
        self.assertGreater(len(buttons), 10)
        for b in buttons:
            self.assertEqual(b.focusPolicy(), Qt.FocusPolicy.TabFocus,
                             b.text() or b.accessibleName())

    def test_every_scroll_area_and_tab_widget_says_what_it_holds(self):
        """Both reached a screen reader as an unnamed "filler": the scroll
        areas as Tab stops, the tab widgets as the tab bars' parents."""
        from PyQt6.QtWidgets import QScrollArea, QTabWidget
        unnamed = [w for w in (self._win.findChildren(QScrollArea)
                               + self._win.findChildren(QTabWidget))
                   if not w.accessibleName()
                   and w.focusPolicy() != w.focusPolicy().NoFocus]
        self.assertEqual(unnamed, [])
        self.assertEqual(self._win._side_tabs.accessibleName(), "Side panel")

    def test_f6_moves_between_the_panel_and_the_map(self):
        from PyQt6.QtWidgets import QApplication
        panel_widget = self._win.plant_panel.picker.view
        self.addCleanup(self._win._side_tabs.setCurrentIndex,
                        self._win._side_tabs.currentIndex())
        self._win._side_tabs.setCurrentIndex(1)
        self._focus_on(panel_widget)
        self._win._panes.switch()
        self._app.processEvents()
        focus = QApplication.focusWidget()
        if focus is None:
            self.skipTest("the map's view took no focus on this platform")
        self.assertTrue(self._win.map_widget.isAncestorOf(focus)
                        or focus is self._win.map_widget)
        self._win._panes.switch()
        self._app.processEvents()
        self.assertIs(QApplication.focusWidget(), panel_widget)

    def test_the_map_and_the_widget_that_takes_its_focus_are_named(self):
        """QtWebEngine's render widget is what Tab lands on, and it read as an
        unnamed "filler"; a new one arrives whenever the renderer restarts."""
        from PyQt6.QtWidgets import QWidget
        view = self._win.map_widget
        self.assertEqual(view.accessibleName(), "Map")
        arriving = QWidget(view)
        self.addCleanup(arriving.deleteLater)
        arriving.ensurePolished()           # what showing it does
        self.assertEqual(arriving.accessibleName(), "Map")

    def test_help_lists_the_keys(self):
        from PyQt6.QtGui import QAction
        names = [a.text().replace("&", "") for a in self._win.findChildren(QAction)]
        self.assertIn("Keyboard Shortcuts…", names)
        from src import keyboard_help
        page = keyboard_help.help_html(self._win)
        self.assertIn("Undo", page)            # read from the menus
        self.assertIn("<b>B</b>", page)

    def test_no_key_is_bound_twice_in_the_window(self):
        """Qt does not drop a duplicate binding: it calls the two ambiguous and
        fires neither. Redo bound Ctrl+Shift+Z itself and again inside the
        platform's Redo keys, so the key on its toolbar tooltip did nothing
        ("Ambiguous shortcut overload", measured V3.02). A key bound only
        inside one widget (WidgetShortcut) is that widget's and is skipped."""
        from collections import defaultdict
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QAction, QShortcut
        widget_only = Qt.ShortcutContext.WidgetShortcut
        owners = defaultdict(list)
        for action in self._win.findChildren(QAction):
            if action.shortcutContext() == widget_only:
                continue
            for seq in action.shortcuts():
                if not seq.isEmpty():
                    owners[seq.toString()].append(action.text())
        for shortcut in self._win.findChildren(QShortcut):
            if shortcut.context() == widget_only:
                continue
            for seq in shortcut.keys():
                if not seq.isEmpty():
                    owners[seq.toString()].append(type(shortcut.parent()).__name__)
        twice = {key: who for key, who in owners.items() if len(who) > 1}
        self.assertEqual(twice, {})

    def test_esc_with_focus_on_the_place_button_stops_placing(self):
        """Pressing Place leaves keyboard focus in the panel, not the map; Esc
        must still stand everything down (MainWindow.keyPressEvent)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        win = self._win
        panel = win.plant_panel
        panel._results_list.setCurrentIndex(
            panel._results_list.model().index(0, 0))
        panel._place_btn.click()
        self.assertEqual(win._current_mode, "plant")
        QTest.keyClick(panel._place_btn, Qt.Key.Key_Escape)
        self.assertEqual(win._current_mode, "none")
        self.assertEqual(win.placement_bar.source, "")
        self.assertFalse(panel._armed)

    def test_the_map_leaving_placing_stands_everything_down(self):
        """Esc in the map: the real bridge signal, through the real wiring."""
        from src.db.plants import search_plants
        win = self._win
        panel = win.plant_panel
        panel._place_plant(search_plants(query="bergamot")[0])
        self.assertEqual(win._current_mode, "plant")
        self.assertEqual(win.placement_bar.source, "plants")

        win.map_widget.bridge.onModeChanged("none", win.map_widget.mode_seq)

        self.assertEqual(win._current_mode, "none")
        self.assertFalse(panel._armed)
        self.assertEqual(win.placement_bar.source, "")
        self.assertEqual(win._sb_mode.text(), "Mode: Ready")

    def test_a_community_pattern_steps_at_community_spacing(self):
        """It stepped at its preview member's own spacing: a 4.65 m row laid 16
        two-metre communities 0.3 m apart."""
        from src.db import polycultures
        win = self._win
        pc = next(p for p in (polycultures.get_polyculture_by_id(r["id"])
                              for r in polycultures.get_all_polycultures())
                  if p and p.get("members"))
        pc = dict(pc, pattern={"kind": "row", "spacing_m": 3.5, "params": {}})
        sent = []
        original = win.map_widget.set_mode
        win.map_widget.set_mode = lambda *a, **k: sent.append((a, k))
        try:
            win._enter_polyculture_mode(pc)
        finally:
            win.map_widget.set_mode = original
            win._cancel_draw()
        args, _kwargs = sent[-1]
        self.assertEqual(args[0], "plant")
        self.assertAlmostEqual(args[3], 3.5)

    # ── What can be seen (F195, V3.03), on every side tab ────────────────────

    def _every_tab(self):
        """The window at a laptop's size, each side tab and sub-tab in turn,
        put back as found: later tests expect Browse to be the Plants page."""
        from PyQt6.QtWidgets import QTabWidget
        from tests import _visual
        win = self._win
        win.resize(1366, 768)
        win.show()
        self._app.processEvents()
        for tabs in [win._side_tabs] + win._side_tabs.findChildren(QTabWidget):
            self.addCleanup(tabs.setCurrentIndex, tabs.currentIndex())
        return _visual.every_tab(win, win._side_tabs)

    def _shown(self):
        """Widgets actually on screen: shown, and not scrolled out of view."""
        from PyQt6.QtWidgets import QWidget
        return [w for w in self._win._side_tabs.findChildren(QWidget)
                if w.isVisible() and not w.visibleRegion().isEmpty()]

    def test_no_text_under_12px_on_any_tab(self):
        """Plant Communities drew 19 of its 21 pieces of text under 12 px and
        Field Notes 21 of 23 (V3.02); rich text's own sizes count too."""
        from tests import _visual
        small = []
        for tab in self._every_tab():
            for w in self._shown():
                words = _visual.plain(_visual.text_of(w))
                if words and _visual.smallest_px(w) < 12:
                    small.append(f"{tab}: {words[:30]!r} {_visual.smallest_px(w)}px")
        self.assertEqual(small, [])

    def test_enabled_text_holds_its_contrast_on_every_tab(self):
        """4.5:1 for text and 3:1 for a graphic (a swatch, a progress dot),
        against the ground read from the window as drawn. Disabled controls
        are exempt (WCAG 1.4.3) and meant to recede."""
        from tests import _visual
        low = []
        for tab in self._every_tab():
            image = self._win.grab().toImage()
            for w in self._shown():
                text = _visual.text_of(w)
                if not w.isEnabled() or not _visual.plain(text):
                    continue
                ground = _visual.ground(image, self._win, w)
                if ground is None:
                    continue
                for colour, graphic in _visual.colours(w):
                    ratio = _visual.contrast(colour, ground)
                    if ratio < (3.0 if graphic else 4.5):
                        low.append(f"{tab}: {_visual.plain(text)[:28]!r} "
                                   f"{colour.name()} on {ground.name()} {ratio:.2f}")
        self.assertEqual(low, [])

    def test_every_checkbox_can_be_seen_on_every_tab(self):
        """An unchecked box's edge was 1.11:1 under Fusion (V3.03): nothing
        said there was a box until it was ticked. 3:1 (WCAG 1.4.11), enabled
        ones; a disabled control is exempt."""
        from PyQt6.QtWidgets import QCheckBox, QRadioButton
        from tests import _visual
        faint = []
        for tab in self._every_tab():
            image = self._win.grab().toImage()
            for w in self._shown():
                if isinstance(w, (QCheckBox, QRadioButton)) and w.isEnabled():
                    seen = _visual.indicator(image, self._win, w)
                    if seen is None:
                        continue
                    edge, ground, _inside = seen
                    ratio = _visual.contrast(edge, ground)
                    if ratio < 3.0:
                        faint.append(f"{tab}: {(w.text() or w.accessibleName())[:28]!r} "
                                     f"{edge.name()} on {ground.name()} {ratio:.2f}")
        self.assertEqual(faint, [])

    def test_every_control_is_24px_on_every_tab(self):
        from PyQt6.QtWidgets import QTabBar
        from src import target_size
        small = []
        for tab in self._every_tab():
            for w in self._shown():
                if (isinstance(w, QTabBar) or target_size.counts(w)) \
                        and min(w.width(), w.height()) < target_size.MIN_TARGET:
                    small.append(f"{tab}: {type(w).__name__} "
                                 f"{(getattr(w, 'text', lambda: '')() or w.accessibleName())[:20]!r} "
                                 f"{w.width()}x{w.height()}")
        self.assertEqual(small, [])

    def test_no_tab_scrolls_sideways(self):
        """At 12 px Plant Communities' row of five buttons needed 444 px and
        Bees' dropdown 441, in a panel 424 wide (first build of V3.03).

        It depends on the font, so it is only as strict as the font the run
        draws in. CI's runner draws in DejaVu Sans, about 12% wider than the
        Arial-metric fonts of Windows: the second build passed under Arial
        metrics and, in DejaVu, Field Notes' questions needed 424 px of 402
        and Plant Communities' title row 470 of 424."""
        from PyQt6.QtWidgets import QScrollArea
        wide = []
        for tab in self._every_tab():
            self.assertGreaterEqual(self._win._side_tabs.width(), 380, tab)
            for area in self._win._side_tabs.findChildren(QScrollArea):
                if area.isVisible() and area.widget() is not None:
                    need = area.widget().minimumSizeHint().width()
                    if need > area.viewport().width():
                        wide.append(f"{tab}: needs {need}, has {area.viewport().width()}")
        self.assertEqual(wide, [])

    def test_community_members_are_coloured_as_a_reload_draws_them(self):
        """By layer until the design was reopened, when the loader drew them by
        type (persistence.py). Placing now passes what the loader passes."""
        from src.db import plants as plants_db
        win = self._win
        rows = plants_db.get_all_plants()[:2]
        community = {"name": "Test community", "members": [
            {"plant_id": r["id"], "common_name": r["common_name"],
             "offset_x": i * 1.0, "offset_y": 0.0, "layer": "overstory"}
            for i, r in enumerate(rows)]}
        drawn = []
        win.map_widget.place_plant_marker = (
            lambda pid, *a, **k: drawn.append((pid, k.get("color"))))
        self.addCleanup(delattr, win.map_widget, "place_plant_marker")
        self._leave_the_window_as_found()
        self.addCleanup(win._store.remove_polyculture, "Test community", 53.5, -113.5)
        win._pending_polyculture = community
        win._current_mode = "polyculture"
        self.addCleanup(setattr, win, "_current_mode", "none")
        win._map_events._on_polyculture_click(53.5, -113.5)
        self.assertEqual(len(drawn), 2)
        for pid, colour in drawn:
            self.assertEqual(colour, win._plant_info(pid)[2])
            self.assertNotEqual(colour, "#1b5e20")     # the old overstory green


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TestGenerateDesignDialog(unittest.TestCase):
    """The goal-selection dialog stands alone (no MainWindow needed)."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def test_one_checkbox_per_goal_and_getters(self):
        from src.generate_design_dialog import GenerateDesignDialog
        from src.design_goals import GOALS
        dlg = GenerateDesignDialog(has_boundary=True, has_pin=False,
                                   preselected=["native_only"])
        try:
            self.assertEqual(len(dlg._checks), len(GOALS))
            self.assertTrue(dlg._checks["native_only"].isChecked())
            self.assertIn("native_only", dlg.selected_goals())
            self.assertFalse(dlg.offline())
        finally:
            dlg.deleteLater()

    def test_ok_disabled_without_location(self):
        from src.generate_design_dialog import GenerateDesignDialog
        from PyQt6.QtWidgets import QDialogButtonBox
        dlg = GenerateDesignDialog(has_boundary=False, has_pin=False)
        try:
            box = dlg.findChild(QDialogButtonBox)
            ok = box.button(QDialogButtonBox.StandardButton.Ok)
            self.assertFalse(ok.isEnabled())
        finally:
            dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
