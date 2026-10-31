"""
tests/test_growth_snapshot_years.py — Growth Snapshots' years, said the same
everywhere (V3.19, QF-13, R28).

Share › Export said the window shows the design "at 1, 5, 15 and 30 years".
The window stops at the year the slowest plant is full grown
(``snapshot_timeline.snapshot_years``), so for the worked example it drew 1, 5,
15 and 20. The line now reads its years from ``project_years``, the rule the
window renders by, and reads them again as the design changes.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = tempfile.mkdtemp(prefix="sp_snapshot_years_")
import src.db.plants as _plants_mod  # noqa: E402
_plants_mod._DATA_DIR = _TMP
_plants_mod._DB_PATH = os.path.join(_TMP, "snapshot_years.db")

try:
    from PyQt6.QtWidgets import QApplication
    _HAVE_QT = True
except ImportError:                                        # pragma: no cover
    _HAVE_QT = False


def _example():
    from src.onboarding import build_example_project
    project, missing = build_example_project()
    assert not missing, missing
    return project


class _Main:
    """What the panel and the window read off the main window."""

    def __init__(self, project):
        self._project = project


class TestTheYearsSaid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _plants_mod.init_db()

    def test_the_example_stops_at_twenty(self):
        from src.share_panel import snapshots_gives
        from src.snapshot_timeline import build_snapshots
        project = _example()
        drawn = [s["year"] for s in build_snapshots(project)]
        self.assertEqual(drawn, [1, 5, 15, 20])
        self.assertEqual(snapshots_gives(project),
                         "the design at years 1, 5, 15 and 20")

    def test_the_line_follows_a_slower_plant(self):
        from src.db.plants import search_plants
        from src.project_store import ProjectStore
        from src.share_panel import snapshots_gives
        from src.snapshot_timeline import project_years
        project = _example()
        spruce = search_plants(query="White Spruce")[0]
        ProjectStore(project).add_plant(spruce["id"], spruce["common_name"],
                                        53.5461, -113.4938)
        years = project_years(project)
        self.assertEqual(years[-1], 25)
        self.assertIn("and 25", snapshots_gives(project))

    def test_no_design_says_what_the_empty_window_shows(self):
        from src.share_panel import snapshots_gives
        from src.snapshot_timeline import project_years
        self.assertEqual(project_years({"features": []}), [1, 5, 15, 20])
        self.assertEqual(snapshots_gives(None),
                         "the design at years 1, 5, 15 and 20")


@unittest.skipUnless(_HAVE_QT, "PyQt6 not installed in this env")
class TestTheLineAndTheWindowAgree(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication(["sp-snap-years"])
        _plants_mod.init_db()

    def test_share_says_what_the_window_draws_for_the_example(self):
        from src.share_panel import SharePanel
        from src.snapshot_timeline import listed_years
        from src.snapshot_window import SnapshotWindow
        main = _Main(_example())
        panel = SharePanel(main)
        self.addCleanup(panel.close)
        window = SnapshotWindow(main)
        self.addCleanup(window.close)
        window.refresh()
        drawn = [c._year for c in window._canvases if c._year]
        self.assertEqual(drawn, [1, 5, 15, 20])
        self.assertIn(listed_years(drawn), window._intro.text())
        # The button's tooltip repeats the line, and was there before it.
        tip = panel.buttons["Growth Snapshots…"].toolTip()
        self.assertIn(listed_years(drawn), tip.lower())
        self.assertNotIn("30", tip)
        said = panel.notes["Growth Snapshots…"].text()
        self.assertIn(listed_years(drawn), said)
        self.assertEqual(tip, said[0].upper() + said[1:])

    def test_the_line_is_read_again_when_the_page_shows(self):
        from src.db.plants import search_plants
        from src.project_store import ProjectStore
        from src.share_panel import SharePanel
        main = _Main(_example())
        panel = SharePanel(main)
        self.addCleanup(panel.close)
        note = panel.notes["Growth Snapshots…"]
        self.assertIn("and 20", note.text())
        oak = search_plants(query="Bur Oak")[0]
        ProjectStore(main._project).add_plant(oak["id"], oak["common_name"],
                                              53.5461, -113.4938)
        panel.show()
        self._app.processEvents()
        self.assertIn("and 30", note.text())
        # And after an edit while it is on screen, once the edits pause.
        main._project = _example()
        panel.design_changed()
        panel._follow.timeout.emit()
        self.assertIn("and 20", note.text())

    def test_an_edit_reaches_the_panel(self):
        from unittest import mock
        from src import follow_design
        main = mock.Mock(_scene3d_window=None, _snapshot_window=None)
        follow_design.request_sync(main)
        main.share_panel.design_changed.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
