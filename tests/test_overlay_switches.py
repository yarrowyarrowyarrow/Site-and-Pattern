"""
tests/test_overlay_switches.py — a switch with nothing to change says what it
needs (V3.19, QF-19, R27).

The click pass found 13 overlay options that were enabled and did nothing
when clicked. Nine of them change an overlay that was not drawn: the sun
path's two shadow options, the wind overlay's two, and the relationship web's
five filters. Each is now disabled until its overlay is on the map, with a
tooltip (and a screen reader's description) saying what to do first, and
enabled once it is, however the overlay came or went: the page's button, the
map's own menu, File › New. The wind's two now also redraw a drawn overlay,
which they never did. The other four, on Slope, choose what Generate draws, so
they stay offered and say when they apply.

Builds a real MainWindow; skips without PyQt6 and its WebEngine.
"""

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_overlay_switches_test_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = os.path.join(_TMP_DIR, "config.json")
except Exception:                                    # pragma: no cover
    pass


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                                # noqa: BLE001
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class OverlaySwitches(unittest.TestCase):

    _win = None
    _error = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["overlay-switches"])
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
        from src import overlay_switches as S
        self.S = S
        self.a = self._win.analysis_panel
        # Every test starts with nothing drawn.
        self._win.map_widget.clear_sun_path()
        self._win.map_widget.clear_wind_overlay()
        self.a._web_toggle.setChecked(False)
        self.addCleanup(self._win._clear_undo)

    def _offered(self, boxes, need):
        for box in boxes:
            self.assertTrue(box.isEnabled(), box.text())
            self.assertNotEqual(box.toolTip(), need, box.text())

    def _held(self, boxes, need):
        for box in boxes:
            self.assertFalse(box.isEnabled(), box.text())
            self.assertEqual(box.toolTip(), need, box.text())
            self.assertEqual(box.accessibleDescription(), need, box.text())
            self.assertTrue(box.text(), "a disabled switch still has a name")

    # ── Sun & Shade ──────────────────────────────────────────────────────────

    def test_the_shadow_options_wait_for_the_sun_path(self):
        win, a = self._win, self.a
        boxes = (a._sun_shadows, a._sun_shadow_length)
        self._held(boxes, self.S.SUN_FIRST)
        win._render_sun_path(a._sun_config(), 53.5461, -113.4938)
        self._offered(boxes, self.S.SUN_FIRST)
        # And they change it then: a click redraws the path as it is.
        with mock.patch.object(win.map_widget, "draw_sun_path") as draw:
            a._sun_shadow_length.toggle()
        draw.assert_called_once()
        self.assertEqual(draw.call_args[0][0]["show_shadow_length"],
                         a._sun_shadow_length.isChecked())
        a._sun_shadow_length.toggle()
        # Removed from the map's own menu: Python is told, and they wait again.
        win.map_widget.bridge.sun_path_removed.emit()
        self._held(boxes, self.S.SUN_FIRST)

    def test_a_new_design_takes_the_sun_path_and_the_switches_with_it(self):
        win, a = self._win, self.a
        win._render_sun_path(a._sun_config(), 53.5461, -113.4938)
        self.assertTrue(a._sun_shadows.isEnabled())
        win._modified = False
        with mock.patch("src.app.QInputDialog.getText",
                        return_value=("Test yard", True)):
            win._on_new()
        self._held((a._sun_shadows, a._sun_shadow_length), self.S.SUN_FIRST)

    # ── Wind ─────────────────────────────────────────────────────────────────

    def test_the_wind_options_wait_for_the_overlay_then_redraw_it(self):
        win, a = self._win, self.a
        boxes = (a._wind_arrows, a._wind_shelter)
        self._held(boxes, self.S.WIND_FIRST)
        own = a._wind_shelter.property(self.S._OWN_TIP)
        with mock.patch.object(win.map_widget, "run_js") as run:
            a._on_show_wind()
            self._offered(boxes, self.S.WIND_FIRST)
            self.assertEqual(a._wind_shelter.toolTip(), own)   # its own again
            run.reset_mock()
            a._wind_arrows.toggle()                            # now it acts
            drawn = [c[0][0] for c in run.call_args_list
                     if c[0][0].startswith("drawWindOverlay(")]
            self.assertEqual(len(drawn), 1)
            self.assertIn('\\"show_arrows\\": false', drawn[0])
            a._wind_arrows.toggle()
            a.wind_cleared.emit()                              # Clear
        self._held(boxes, self.S.WIND_FIRST)
        # Ticked or not while it waits, it draws nothing.
        with mock.patch.object(win.map_widget, "run_js") as run:
            a._wind_arrows.setChecked(not a._wind_arrows.isChecked())
            a._wind_arrows.setChecked(not a._wind_arrows.isChecked())
        self.assertFalse([c for c in run.call_args_list
                          if c[0][0].startswith("drawWindOverlay(")])

    # ── Habitat › the relationship web ───────────────────────────────────────

    def test_the_web_filters_wait_for_the_web(self):
        a = self.a
        boxes = tuple(a._web_layer_boxes.values())
        self.assertEqual(len(boxes), 5)
        self._held(boxes, self.S.WEB_FIRST)
        a._web_toggle.setChecked(True)
        self._offered(boxes, self.S.WEB_FIRST)
        a._web_toggle.setChecked(False)
        self._held(boxes, self.S.WEB_FIRST)

    def test_a_held_web_filter_looks_held(self):
        """Its own stylesheet named one colour for every state, so a disabled
        filter read exactly like an offered one."""
        box = next(iter(self.a._web_layer_boxes.values()))
        self.assertIn("QCheckBox:disabled", box.styleSheet())
        from src.ui_style import APP_STYLE
        self.assertIn("QCheckBox:disabled", APP_STYLE)
        self.assertIn("QMenu::item:disabled", APP_STYLE)

    # ── Slope: Generate's options, offered, and saying so ────────────────────

    def test_the_slope_options_say_they_apply_on_generate(self):
        sp = self._win.site_panel
        for box in (sp._auto_want_contours, sp._auto_want_slope,
                    sp._auto_want_water, sp._auto_show_labels):
            self.assertTrue(box.isEnabled(), box.text())
            self.assertIn("Applies when you press Generate", box.toolTip(),
                          box.text())


if __name__ == "__main__":
    unittest.main()
