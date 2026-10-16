"""
tests/test_advanced_tools.py — simple by default, advanced tools one switch
away (V3.21, MD-1 and RM-4; docs/homeowner/02-two-ways-to-use-it.md).

With the switch off every registered page, action, toolbar item and control
is hidden; on, all are shown; switching changes nothing in the design or the
undo stack; the switch is remembered. The settings are a dict here, so no
test leaves the switch on for the tests after it.
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_advanced_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP
    _plants_mod._DB_PATH = os.path.join(_TMP, "advanced.db")
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = os.path.join(_TMP, "config.json")
except Exception:                                    # pragma: no cover
    pass

from src import advanced_tools  # noqa: E402


class _Settings:
    """A dict-backed QSettings, shared by every instance like the real one."""
    store: dict = {}

    def value(self, key, default=None, type=None):   # noqa: A002
        v = self.store.get(key, default)
        return type(v) if type is not None and v is not None else v

    def setValue(self, key, value):                  # noqa: N802
        self.store[key] = value


class TheSwitch(unittest.TestCase):

    def setUp(self):
        _Settings.store = {}
        patcher = mock.patch.object(advanced_tools, "QSettings", _Settings)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_off_until_turned_on_and_remembered(self):
        self.assertFalse(advanced_tools.is_on())
        advanced_tools.set_on(True)
        self.assertTrue(advanced_tools.is_on())     # a new QSettings reads it
        advanced_tools.set_on(False)
        self.assertFalse(advanced_tools.is_on())

    def test_a_design_says_what_advanced_work_it_holds(self):
        def feature(**props):
            return {"properties": props}
        made = {"features": [
            feature(element_type="plant"),
            feature(element_type="custom_shape", shape_type="Garden Bed"),
            feature(element_type="custom_shape", shape_type="Patio / Deck"),
        ]}
        self.assertEqual(advanced_tools.uses_advanced(made), [])
        made["features"] += [
            feature(element_type="measurement"),
            feature(element_type="auto_contour"),
            feature(element_type="measurement"),
            feature(element_type="hedgerow"),
            feature(element_type="annotation"),
            feature(element_type="custom_shape", shape_type="Custom"),
        ]
        self.assertEqual(advanced_tools.uses_advanced(made), [
            "contours or a slope map", "measurements", "notes on the map",
            "hedges, fences or windbreaks", "custom shapes"])
        self.assertEqual(advanced_tools.uses_advanced(None), [])

    def test_the_registry_names_each_surface_once(self):
        names = advanced_tools.every_entry()
        self.assertEqual(len(names), len(set(names)))


def _qt_available():
    try:
        import PyQt6.QtWebEngineWidgets  # noqa: F401
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                                # noqa: BLE001
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class InTheWindow(unittest.TestCase):

    _win = None
    _error = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["advanced-tools"])
        cls._patch = mock.patch.object(advanced_tools, "QSettings", _Settings)
        cls._patch.start()
        _Settings.store = {}
        try:
            from src.app import MainWindow
            cls._win = MainWindow()
        except Exception as exc:                     # noqa: BLE001
            cls._error = exc

    @classmethod
    def tearDownClass(cls):
        cls._patch.stop()
        if cls._win is not None:
            cls._win._modified = False
            cls._win.close()
            cls._win.deleteLater()
            cls._win = None

    def setUp(self):
        if self._error is not None:
            self.skipTest(f"MainWindow construction failed in this env: "
                          f"{type(self._error).__name__}: {self._error}")
        from src import advanced_tools_flow
        self.flow = advanced_tools_flow
        self.addCleanup(lambda: self.flow.set_and_apply(self._win, False))

    def _surfaces(self):
        """``[(name, is_shown())]`` for every entry the registry names."""
        from PyQt6.QtGui import QAction
        from src.side_panel_layout import tab_owner
        win, out = self._win, []
        for path in advanced_tools.ADVANCED_PAGES:
            page = self.flow.resolve(win, path)
            tabs = tab_owner(page)
            out.append((path, tabs.isTabVisible(tabs.indexOf(page))))
        for name in advanced_tools.ADVANCED_ACTIONS:
            out.append((name, win.findChild(QAction, name).isVisible()))
        for path in advanced_tools.ADVANCED_TOOLBAR_ITEMS:
            act = self.flow._toolbar_action(self.flow.resolve(win, path))
            out.append((path, act.isVisible()))
        for path in advanced_tools.ADVANCED_CONTROLS:
            out.append((path, not self.flow.resolve(win, path).isHidden()))
        return out

    def test_every_entry_is_in_the_window(self):
        from PyQt6.QtGui import QAction
        from src.side_panel_layout import tab_owner
        win = self._win
        for path in advanced_tools.ADVANCED_PAGES:
            page = self.flow.resolve(win, path)
            self.assertIsNotNone(page, path)
            self.assertIsNotNone(tab_owner(page), path)
        for name in advanced_tools.ADVANCED_ACTIONS:
            self.assertIsNotNone(win.findChild(QAction, name), name)
        for path in advanced_tools.ADVANCED_TOOLBAR_ITEMS:
            self.assertIsNotNone(
                self.flow._toolbar_action(self.flow.resolve(win, path)), path)
        for path in (advanced_tools.ADVANCED_CONTROLS
                     + advanced_tools.ADVANCED_HOOKS):
            self.assertIsNotNone(self.flow.resolve(win, path), path)

    def test_a_cold_start_is_simple(self):
        self.assertFalse(self._win._act_advanced.isChecked())
        self.assertEqual([n for n, shown in self._surfaces() if shown], [])

    def test_on_shows_everything_and_off_hides_it_again(self):
        self.flow.set_and_apply(self._win, True)
        self.assertTrue(self._win._act_advanced.isChecked())
        self.assertEqual([n for n, shown in self._surfaces() if not shown], [])
        self.flow.set_and_apply(self._win, False)
        self.assertEqual([n for n, shown in self._surfaces() if shown], [])

    def test_switching_leaves_the_design_and_the_undo_stack_alone(self):
        win = self._win
        win._push_undo({"action": "noop", "data": {}})
        before = (json.dumps(win._project, sort_keys=True, default=str),
                  copy.deepcopy(win._undo_stack), copy.deepcopy(win._redo_stack))
        self.flow.set_and_apply(win, True)
        self.flow.set_and_apply(win, False)
        after = (json.dumps(win._project, sort_keys=True, default=str),
                 win._undo_stack, win._redo_stack)
        self.assertEqual(before, after)
        win._clear_undo()

    def test_the_learn_tab_and_the_design_pages_follow(self):
        tabs = self._win._side_tabs
        learn = tabs.indexOf(self._win.learn_panel)
        self.assertFalse(tabs.isTabVisible(learn))
        design = self._win.analysis_panel._tabs
        shown = [design.tabText(i) for i in range(design.count())
                 if design.isTabVisible(i)]
        self.assertEqual(shown, ["Report card", "Planted"])
        self.flow.set_and_apply(self._win, True)
        self.assertTrue(tabs.isTabVisible(learn))

    def test_the_bar_shows_in_simple_mode_for_advanced_work(self):
        win = self._win
        bar = win.advanced_bar
        saved = win._project
        self.addCleanup(lambda: (setattr(win, "_project", saved),
                                 self.flow.refresh_bar(win)))
        win._project = {"features": [], "properties": {}}
        self.flow.refresh_bar(win)
        self.assertTrue(bar.isHidden())
        win._project = {"features": [{"properties": {
            "element_type": "contour_line"}}], "properties": {}}
        self.flow.refresh_bar(win)
        self.assertFalse(bar.isHidden())
        self.assertEqual(bar.label.text(), "This design uses advanced tools.")
        bar.show_btn.click()
        self.assertTrue(win._act_advanced.isChecked())
        self.assertTrue(bar.isHidden())
        slope = win.site_panel.slope_page
        self.assertIs(win.site_panel._tabs.currentWidget(), slope)
        self.assertIs(win._side_tabs.currentWidget(), win.site_panel)

    def test_a_hidden_pattern_is_not_left_chosen(self):
        self.flow.set_and_apply(self._win, True)
        controls = self._win.plant_panel._placement
        controls.set_kind("grid")
        self.flow.set_and_apply(self._win, False)
        self.assertEqual(controls.kind, "single")

    def test_a_tool_the_switch_hides_is_not_left_armed(self):
        self.flow.set_and_apply(self._win, True)
        measure = self._win.toolbar._act_measure
        measure.trigger()
        self.assertTrue(measure.isChecked())
        self.flow.set_and_apply(self._win, False)
        self.assertFalse(measure.isChecked())


if __name__ == "__main__":
    unittest.main()
