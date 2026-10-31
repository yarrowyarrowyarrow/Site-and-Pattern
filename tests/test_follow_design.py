"""
tests/test_follow_design.py — the windows that show the design follow it
(F89, V3.08), and wear the app's dark surface (F209).

The 3D preview's *Refresh from design* and Growth Snapshots' *Refresh* were
manual syncs: edit the map, and both showed the old design until pressed. The
owner said yes to the preview following edits; Snapshots follows by the same
rule. ``src/follow_design.py`` is the rule; these tests drive it with stand-in
windows, and the real windows' own tests check they have no Refresh left.
"""

import os
import pathlib
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_ROOT = pathlib.Path(__file__).resolve().parent.parent

try:
    from PyQt6.QtWidgets import QApplication, QWidget
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


if _HAVE_QT:
    class _Window(QWidget):
        """Counts its rebuilds, under either method name the rule calls."""

        def __init__(self, fail=False):
            super().__init__()
            self.rebuilt = 0
            self._fail = fail

        def follow_design(self):
            self.rebuilt += 1
            if self._fail:
                raise RuntimeError("a scene that will not build")

        refresh = follow_design


class _Main:
    pass


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestFollowDesign(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-follow"])

    def _wait(self):
        from PyQt6.QtTest import QTest
        from src.follow_design import DELAY_MS
        QTest.qWait(DELAY_MS + 150)

    def _main(self, **windows):
        main = _Main()
        for attr, win in windows.items():
            setattr(main, attr, win)
            self.addCleanup(win.close)
        return main

    def test_a_burst_of_edits_is_one_rebuild_of_each_open_window(self):
        from src import follow_design
        preview, snaps = _Window(), _Window()
        preview.show()
        snaps.show()
        main = self._main(_scene3d_window=preview, _snapshot_window=snaps)
        for _ in range(6):                  # a drag's worth of moves
            follow_design.request_sync(main)
        self.assertEqual(preview.rebuilt, 0, "rebuilt before the edits paused")
        self._wait()
        self.assertEqual((preview.rebuilt, snaps.rebuilt), (1, 1))

    def test_a_closed_window_pays_nothing(self):
        from src import follow_design
        preview = _Window()                 # never shown
        main = self._main(_scene3d_window=preview)
        follow_design.request_sync(main)
        self._wait()
        self.assertEqual(preview.rebuilt, 0)
        self.assertIsNone(getattr(preview, "_follow_timer", None))

    def test_no_window_open_is_not_an_error(self):
        from src import follow_design
        follow_design.request_sync(_Main())

    def test_an_edit_made_in_the_preview_is_not_rebuilt_twice(self):
        from src import follow_design
        preview = _Window()
        preview.show()
        main = self._main(_scene3d_window=preview)
        follow_design.request_sync(main)    # the edit's _mark_modified
        follow_design.settled(preview)      # the preview pushed it itself
        self._wait()
        self.assertEqual(preview.rebuilt, 0)

    def test_a_rebuild_that_fails_does_not_end_the_app(self):
        """From a timer: an exception escaping a Qt slot aborts the process."""
        from src import follow_design
        preview = _Window(fail=True)
        preview.show()
        main = self._main(_scene3d_window=preview)
        follow_design.request_sync(main)
        self._wait()
        self.assertEqual(preview.rebuilt, 1)

    def test_every_edit_and_every_opened_design_reaches_it(self):
        """The two places every change already passes: _mark_modified (each
        edit, split view's hook since V2.44) and _sync_planning_panel (a
        design opened, an undo)."""
        persistence = (_ROOT / "src" / "controllers" / "persistence.py"
                       ).read_text(encoding="utf-8")
        mark = persistence[persistence.index("def _mark_modified"):]
        mark = mark[:mark.index("\n    def ")]
        self.assertIn("follow_design.request_sync(self._main)", mark)
        app = (_ROOT / "src" / "app.py").read_text(encoding="utf-8")
        sync = app[app.index("def _sync_planning_panel"):]
        sync = sync[:sync.index("\n    def ")]
        self.assertIn("follow_design.request_sync(self)", sync)


class TestOnePrimaryColour(unittest.TestCase):
    """F209: the main action of a page is the app's green, the rest grey.
    The V3.05 audit found orange (Sun & Shade), teal and blue (Wind) primaries
    beside the green everywhere else, three colours for one meaning."""

    def test_no_button_is_filled_in_a_colour_of_its_own(self):
        import colorsys
        fill = re.compile(r"QPushButton\s*\{[^}]*?background(?:-color)?\s*:\s*"
                          r"#([0-9a-fA-F]{6})")
        offenders = []
        for path in sorted((_ROOT / "src").rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            for m in fill.finditer(text):
                r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
                h, _l, s = colorsys.rgb_to_hls(r, g, b)
                hue = h * 360
                # Greens (the app's own), and anything greyish, pass.
                if s > 0.5 and not 80 <= hue <= 160:
                    offenders.append(f"{path.relative_to(_ROOT)}: #{m.group(1)}")
        self.assertEqual(offenders, [])


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheWindowsAreDark(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-follow"])

    def test_growth_snapshots_is_dark_and_has_no_refresh(self):
        from PyQt6.QtWidgets import QPushButton
        from src.snapshot_window import SnapshotWindow
        from src.ui_style import WINDOW_STYLE
        main = _Main()
        main._project = {"type": "FeatureCollection",
                         "properties": {"site_config": {}}, "features": []}
        win = SnapshotWindow(main)
        self.addCleanup(win.close)
        self.assertEqual(win.styleSheet(), WINDOW_STYLE)
        self.assertEqual([b.text() for b in win.findChildren(QPushButton)], [])

    def test_every_window_of_its_own_wears_it(self):
        """The 3D preview, Growth Snapshots and Walk a Wild Landscape are
        top-level, so none inherits the main window's stylesheet; the walk's
        pale-green words sat on light grey, nearly invisible (V3.08's probe)."""
        for name in ("scene3d_window.py", "snapshot_window.py",
                     "reference_ecosystem_window.py"):
            source = (_ROOT / "src" / name).read_text(encoding="utf-8")
            self.assertIn("self.setStyleSheet(WINDOW_STYLE)", source, name)

    def test_the_window_style_is_the_apps_own_surface(self):
        from src.ui_style import APP_STYLE, BASE_SURFACE, WINDOW_STYLE
        self.assertTrue(WINDOW_STYLE.startswith(APP_STYLE))
        ground = re.search(r"background-color:\s*(#[0-9a-f]{6})", BASE_SURFACE)
        self.assertIn(ground.group(1), APP_STYLE)
        self.assertIn("QPushButton:checked", WINDOW_STYLE)


if __name__ == "__main__":
    unittest.main()
