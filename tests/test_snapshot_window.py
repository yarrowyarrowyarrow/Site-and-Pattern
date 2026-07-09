"""
tests/test_snapshot_window.py — the Growth Snapshots window (F2).

Qt-gated smoke tests (skipped where PyQt6 isn't installed, like
tests/test_scene3d_window.py): the window constructs against a minimal fake
main, refresh() fills the four canvases with scenes built from the live
project, and open_snapshot_view keeps a singleton on the main. DB-free — the
fixture uses an existing-tree feature so no plant lookup is needed.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed")
class TestSnapshotWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["permadesign-tests"])

    def _fake_main(self):
        class _Fake:
            pass
        m = _Fake()
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

    def test_refresh_fills_four_canvases(self):
        from src.snapshot_window import SnapshotWindow
        win = SnapshotWindow(self._fake_main())
        win.refresh()
        self.assertEqual(len(win._canvases), 4)
        # Every canvas got a scene and a year, sharing one bounds box.
        # Years are CAPPED at the design's own maturity horizon
        # (snapshot_timeline.snapshot_years → succession.timeline_max_years):
        # this fixture places no plants, so the cap is the 20-year floor and
        # the last snapshot is year 20, not the uncapped 30. (Stale [1,5,15,30]
        # expectation surfaced in V2.22 — the test needs QtWidgets and had
        # never actually run in this container before.)
        years = [c._year for c in win._canvases]
        from src.snapshot_timeline import snapshot_years
        self.assertEqual(years, snapshot_years([]))
        self.assertEqual(years, [1, 5, 15, 20])
        boxes = {id(c._bounds) for c in win._canvases}
        self.assertEqual(len(boxes), 1)
        for c in win._canvases:
            self.assertIsNotNone(c._scene)
        win.deleteLater()

    def test_empty_project_sets_status_and_clears(self):
        from src.snapshot_window import SnapshotWindow
        main = self._fake_main()
        main._project["features"] = []
        win = SnapshotWindow(main)
        win.refresh()
        self.assertIn("No plants", win._status.text())
        win.deleteLater()

    def test_open_snapshot_view_singleton(self):
        from src.snapshot_window import open_snapshot_view
        main = self._fake_main()
        w1 = open_snapshot_view(main)
        w2 = open_snapshot_view(main)
        self.assertIs(w1, w2)
        self.assertIs(main._snapshot_window, w1)
        w1.close()
        w1.deleteLater()


if __name__ == "__main__":
    unittest.main()
