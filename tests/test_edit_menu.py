"""
tests/test_edit_menu.py — the Edit menu, and each item is its twin (V3.19,
QF-15, R33).

The menu bar was File, View and Help from V2.25; a stranger looked for Undo
where every program keeps it. The menu is back with Undo, Redo, Delete and
Select All, and none of them is a second way of doing something:

  * Undo and Redo are the very QActions that carry Ctrl+Z and the Redo keys
    (a second action with the same key makes Qt fire neither) and run what
    the toolbar's buttons run, greyed out with them;
  * Delete runs what the Delete key runs on the map, offered only while the
    page reports a selection;
  * Select All selects what the selection box would catch round the whole
    map, less what a View switch hides, checked in the real page in headless
    Chromium (``html/select_all_probe.html``, the harness
    ``tests/test_boundary_press.py`` uses).
"""

import os
import pathlib
import re
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_edit_menu_test_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = os.path.join(_TMP_DIR, "config.json")
except Exception:                                    # pragma: no cover
    pass

from tests.test_scene3d_render import _find_chromium  # noqa: E402

_MAP = pathlib.Path(__file__).resolve().parent.parent / "html" / "map"


class ThePageHasTheFunctions(unittest.TestCase):
    """Source guards: need neither Qt nor a browser."""

    def setUp(self):
        self.js = "\n".join(p.read_text(encoding="utf-8")
                            for p in sorted(_MAP.glob("*.js")))

    def test_select_all_is_defined(self):
        from src import map_js
        self.assertEqual(map_js.select_all(), "selectAll();")
        self.assertRegex(self.js, r"\bfunction\s+selectAll\s*\(")

    def test_the_selection_count_is_reported_where_the_badge_is_drawn(self):
        body = re.search(r"function _updateSelectionBadge\(\)\s*\{(.*?)\n    \}",
                         self.js, re.S)
        self.assertIsNotNone(body)
        self.assertIn("bridge.onSelectionCount(selectedItems.length)",
                      body.group(1))


@unittest.skipIf(_find_chromium() is None,
                 "no Chromium binary (set CHROME= to run this gate)")
class SelectAllInThePage(unittest.TestCase):
    m = None

    @classmethod
    def setUpClass(cls):
        from tests.test_boundary_press import _run_probe
        cls.m = _run_probe("select_all_probe.html")

    def setUp(self):
        self.assertNotIn("error", self.m, self.m.get("error"))

    def test_everything_shown_is_selected_and_counted(self):
        self.assertEqual(self.m["cleared_count"], 0)
        self.assertEqual(self.m["all"]["kinds"],
                         ["boundary", "measure", "plant", "plant"])
        self.assertEqual(self.m["all"]["count"], 4)
        self.assertEqual(self.m["again"], 4)

    def test_not_only_what_is_in_view(self):
        self.assertEqual(self.m["out_of_view"],
                         ["boundary", "measure", "plant", "plant"])

    def test_then_one_delete_takes_the_lot(self):
        d = self.m["delete"]
        self.assertEqual((d["calls"], d["plants"], d["boundaries"],
                          d["measurements"], d["count"]),
                         (1, 2, ["b1"], ["m1"], 0))

    def test_what_a_view_switch_hides_is_left_alone(self):
        self.assertEqual(self.m["plants_hidden"], ["boundary", "measure"])
        self.assertEqual(self.m["boundary_and_measure_hidden"],
                         ["plant", "plant"])

    def test_an_empty_map_selects_nothing(self):
        self.assertEqual(self.m["empty"], {"kinds": [], "count": 0})

    def test_a_redraw_leaves_nothing_selected(self):
        """clearAll (an open, an undo, File › New) had left the selection
        behind: its badge on an empty map, and Edit › Delete offered."""
        self.assertEqual(self.m["after_redraw"],
                         {"kinds": [], "count": 0, "badge": False})


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                                # noqa: BLE001
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TheMenuInTheWindow(unittest.TestCase):

    _win = None
    _error = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["edit-menu"])
        try:
            from src.app import MainWindow
            cls._win = MainWindow()
        except Exception as exc:                     # noqa: BLE001
            cls._error = exc

    @classmethod
    def tearDownClass(cls):
        if cls._win is not None:
            cls._win._modified = False
            cls._win.close()
            cls._win.deleteLater()
            cls._win = None

    def setUp(self):
        if self._error is not None:
            self.skipTest(f"MainWindow construction failed in this env: "
                          f"{type(self._error).__name__}: {self._error}")
        self.addCleanup(self._win._clear_undo)

    def _menu(self, title):
        for a in self._win.menuBar().actions():
            if a.menu() is not None and a.text().replace("&", "") == title:
                return a.menu()
        self.fail(f"no {title} menu")

    def test_between_file_and_view(self):
        titles = [a.text().replace("&", "")
                  for a in self._win.menuBar().actions()]
        self.assertEqual(titles, ["File", "Edit", "View", "Help"])
        words = [a.text().replace("&", "") for a in self._menu("Edit").actions()
                 if not a.isSeparator()]
        self.assertEqual(words, ["Undo", "Redo", "Delete", "Select All"])

    def test_undo_and_redo_are_the_actions_that_carry_the_keys(self):
        edit = self._menu("Edit").actions()
        self.assertIs(edit[0], self._win._act_undo)
        self.assertIs(edit[1], self._win._act_redo)
        self.assertEqual(self._win._act_undo.shortcut().toString(), "Ctrl+Z")

    def test_each_runs_what_its_toolbar_twin_runs(self):
        win = self._win
        win._clear_undo()
        edit_undo, edit_redo = self._menu("Edit").actions()[:2]
        bar_undo, bar_redo = win.toolbar._act_undo, win.toolbar._act_redo
        for act in (edit_undo, edit_redo, bar_undo, bar_redo):
            self.assertFalse(act.isEnabled(), act.text())   # nothing to undo
        win._push_undo({"action": "noop", "data": {}})
        win._redo_stack.append({"action": "noop", "data": {}})
        win._persistence._sync_undo_actions()
        for act in (edit_undo, edit_redo, bar_undo, bar_redo):
            self.assertTrue(act.isEnabled(), act.text())
        with mock.patch.object(win._persistence, "_do_undo") as undo, \
                mock.patch.object(win._persistence, "_do_redo") as redo:
            bar_undo.trigger()
            edit_undo.trigger()
            bar_redo.trigger()
            edit_redo.trigger()
        self.assertEqual((undo.call_count, redo.call_count), (2, 2))

    def test_delete_is_the_delete_keys_and_waits_for_a_selection(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        from src import keyboard_help
        win = self._win
        delete = win._act_delete
        self.assertFalse(delete.isEnabled())
        self.assertTrue(delete.shortcut().isEmpty())     # the map's key
        win.map_widget.bridge.onSelectionCount(3)
        self.assertTrue(delete.isEnabled())
        with mock.patch.object(win.map_widget, "delete_selected") as gone:
            delete.trigger()
            with mock.patch.object(keyboard_help, "map_has_focus",
                                   return_value=True):
                win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,
                                            Qt.Key.Key_Delete,
                                            Qt.KeyboardModifier.NoModifier))
        self.assertEqual(gone.call_count, 2)
        win.map_widget.bridge.onSelectionCount(0)
        self.assertFalse(delete.isEnabled())

    def test_select_all_selects_on_the_map(self):
        win = self._win
        act = win._act_select_all
        self.assertEqual(act.shortcut().toString(), "Ctrl+A")
        with mock.patch.object(win.map_widget, "run_js") as run:
            act.trigger()
        run.assert_called_once_with("selectAll();")

    def test_ctrl_a_is_the_maps_unless_a_text_box_has_the_keys(self):
        """Pressed in the map, Ctrl+A selects on it (the page lets the key
        through, nothing in it being editable); pressed in a text box, it
        selects the text, which a focused text box claims before the window's
        keys. Both measured in the real window, the page loaded."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QApplication
        win = self._win
        win.show()
        win.activateWindow()
        for _ in range(600):          # the page brings its own focus widget
            self._app.processEvents()
            if win.map_widget.is_ready:
                break
            time.sleep(0.025)
        if not win.map_widget.is_ready:
            self.skipTest("the map page never loaded in this environment")
        # Offscreen, the window shown last is the active one, and earlier
        # tests in a full run leave windows of their own to be shown while
        # the page loads (V3.20): a key pressed then reaches neither the box
        # nor the window's shortcuts. Take the keys back first.
        win.activateWindow()
        QTest.qWaitForWindowActive(win, 2000)
        ran = []
        box = win.site_panel._addr_input
        self.addCleanup(box.clear)
        with mock.patch.object(win.map_widget, "select_all",
                               side_effect=lambda: ran.append("map")):
            box.setText("10050 109 Street")
            win.site_panel.focus_address_search()
            box.deselect()
            self._app.processEvents()
            self.assertIs(QApplication.focusWidget(), box)
            QTest.keyClick(box, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual((ran, box.selectedText()), ([], "10050 109 Street"))

            win.map_widget.setFocus(Qt.FocusReason.OtherFocusReason)
            self._app.processEvents()
            in_map = QApplication.focusWidget()
            self.assertTrue(in_map is win.map_widget
                            or win.map_widget.isAncestorOf(in_map), in_map)
            QTest.keyClick(in_map, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            self._app.processEvents()
        self.assertEqual(ran, ["map"])


if __name__ == "__main__":
    unittest.main()
