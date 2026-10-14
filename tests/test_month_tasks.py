"""
tests/test_month_tasks.py — the status bar names this design's jobs, or none
(V3.19, QF-12, R26).

Before a plant was placed the status bar read "October: Direct Sow: Meadow
Sedge, Yellow Rattle | Harvest: Bog Cranberry, Broad-leaved Arrowhead,
Broomweed +3": the first eight calendar rows of the whole catalogue. These
check the line is the open design's: nothing with no plants, only the worked
example's plants with the example open, and harvest said only of a plant with
edible parts, as the plant page says it.

The pure tests need neither Qt nor the database (the calendar is injected);
the catalogue tests use a temporary database; the window tests build a real
MainWindow and skip without PyQt6 and its WebEngine.
"""

import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP_DIR = tempfile.mkdtemp(prefix="permadesign_month_tasks_test_")
try:
    import src.db.plants as _plants_mod
    _plants_mod._DATA_DIR = _TMP_DIR
    _plants_mod._DB_PATH = os.path.join(_TMP_DIR, "permadesign_test.db")
    import src.settings as _settings_mod
    _settings_mod._CONFIG_PATH = os.path.join(_TMP_DIR, "config.json")
except Exception:                                    # pragma: no cover
    pass

from src import month_tasks  # noqa: E402


class _Label:
    """The status bar label, as far as refresh() uses it."""

    def __init__(self, text="October: something from before"):
        self._text = text

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text


def _rows(*rows):
    """A fetch() that answers with these calendar rows for any plants."""
    def fetch(ids, month):
        return [dict(zip(("plant_id", "common_name", "status",
                          "edible_parts"), r)) for r in rows
                if r[0] in set(ids)]
    return fetch


class TheLineIsWritten(unittest.TestCase):

    def test_no_plants_no_line(self):
        def boom(ids, month):
            raise AssertionError("asked the catalogue with no plants")
        self.assertEqual(month_tasks.jobs_for([], 10, fetch=boom), [])
        self.assertEqual(month_tasks.status_line([], 10), "")

    def test_jobs_in_the_order_the_work_comes(self):
        fetch = _rows((1, "Saskatoon", "pruning", "fruit"),
                      (2, "Wild Bergamot", "transplant", ""),
                      (3, "Meadow Sedge", "direct_sow", None))
        jobs = month_tasks.jobs_for([1, 2, 3], 10, fetch=fetch)
        self.assertEqual([w for w, _n in jobs],
                         ["sow outdoors", "plant out", "prune"])
        self.assertEqual(
            month_tasks.status_line(jobs, 10),
            "To do in October: sow outdoors Meadow Sedge · plant out Wild "
            "Bergamot · prune Saskatoon")

    def test_harvest_only_of_what_can_be_eaten(self):
        """The review's "harvest Broad-leaved Arrowhead": the fruiting season
        said again, for a plant nobody here eats."""
        fetch = _rows((1, "Broad-leaved Arrowhead", "harvest", ""),
                      (2, "Saskatoon", "harvest", "fruit"))
        jobs = month_tasks.jobs_for([1, 2], 8, fetch=fetch)
        self.assertEqual(jobs, [("harvest", ["Saskatoon"])])

    def test_many_plants_end_in_a_count(self):
        names = ["A", "B", "C", "D", "E"]
        fetch = _rows(*[(i, n, "pruning", "") for i, n in enumerate(names)])
        jobs = month_tasks.jobs_for(range(5), 3, fetch=fetch)
        self.assertEqual(month_tasks.status_line(jobs, 3),
                         "To do in March: prune A, B, C and 2 more")
        two = month_tasks.jobs_for([0, 1], 3, fetch=fetch)
        self.assertEqual(month_tasks.status_line(two, 3),
                         "To do in March: prune A and B")

    def test_the_words_are_the_plant_pages(self):
        """One job, one name: the status bar and the plant page."""
        try:
            from src.species_page import _TASKS
        except ImportError as exc:                     # no PyQt6 here
            self.skipTest(f"species_page needs Qt: {exc}")
        page = dict(_TASKS)
        page["harvest"] = "Harvest"            # said of edible plants only
        self.assertEqual({s: w.capitalize() for s, w in month_tasks.JOBS},
                         page)


class TheLineFollowsTheDesign(unittest.TestCase):
    """refresh(), against a stand-in window."""

    def _main(self, *ids):
        return types.SimpleNamespace(
            _sb_tasks=_Label(),
            _placed_plants=[{"plant_id": i} for i in ids])

    def test_no_plants_clears_what_was_there(self):
        main = self._main()
        month_tasks.refresh(main, month=10)
        self.assertEqual(main._sb_tasks.text(), "")

    def test_asks_again_only_when_the_plants_change(self):
        calls = []
        real = month_tasks.jobs_for

        def counting(ids, month, fetch=None):
            calls.append(set(ids))
            return real(ids, month, fetch=_rows((7, "Saskatoon", "pruning",
                                                 "fruit")))
        main = self._main(7)
        orig, month_tasks.jobs_for = month_tasks.jobs_for, counting
        try:
            month_tasks.refresh(main, month=3)
            month_tasks.refresh(main, month=3)           # a drag: same plants
            self.assertEqual(len(calls), 1)
            self.assertEqual(main._sb_tasks.text(),
                             "To do in March: prune Saskatoon")
            main._placed_plants = []
            month_tasks.refresh(main, month=3)
            self.assertEqual(main._sb_tasks.text(), "")
        finally:
            month_tasks.jobs_for = orig


class TheCatalogue(unittest.TestCase):
    """Against the shipped calendar, in a temporary database."""

    @classmethod
    def setUpClass(cls):
        from src.db.plants import init_db
        init_db()
        from src import onboarding
        from src.project_store import ProjectStore
        project, cls.missing = onboarding.build_example_project()
        placed = ProjectStore(project).placed_plants
        cls.ids = {p["plant_id"] for p in placed}
        cls.names = {p["common_name"] for p in placed}

    def test_the_example_resolves(self):
        self.assertEqual(self.missing, [])
        self.assertGreater(len(self.ids), 5)

    def test_only_the_examples_plants_are_named(self):
        from src.db.plants import get_month_tasks
        named, others = set(), set()
        for month in range(1, 13):
            for _words, names in month_tasks.jobs_for(self.ids, month):
                named.update(names)
            others.update(r["common_name"] for r in
                          get_month_tasks(range(1, 5000), month)
                          if r["plant_id"] not in self.ids)
        self.assertTrue(named, "the example has no job in any month")
        self.assertLessEqual(named, self.names)
        # And the catalogue does have jobs for plants not in the example,
        # which is what the old line showed to a design with none of them.
        self.assertTrue(others)

    def test_no_ids_no_rows(self):
        from src.db.plants import get_month_tasks
        self.assertEqual(get_month_tasks([], 10), [])
        self.assertEqual(get_month_tasks(None, 10), [])


def _qt_available():
    try:
        from PyQt6.QtWidgets import QApplication  # noqa: F401
        return True
    except Exception:                                # noqa: BLE001
        return False


@unittest.skipUnless(_qt_available(), "PyQt6 not installed in this env")
class TheWindowsStatusBar(unittest.TestCase):
    """The real window: empty at start, the example's jobs once it is open,
    empty again after File › New."""

    _win = None
    _error = None

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(["month-tasks"])
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

    def test_a_long_line_never_widens_the_window(self):
        """The line is as long as the design's plant list. As a plain QLabel,
        every catalogue plant in October asked for 1,104 px and took the
        window's minimum width from 1,007 to 1,564 px, past a 1366 px screen.
        It is cut to fit with "…", the whole line kept and a hover away."""
        from PyQt6.QtWidgets import QLabel
        win = self._win
        label = win._sb_tasks
        win.resize(1366, 768)
        win.show()
        self._app.processEvents()
        before = win.minimumSizeHint().width()
        line = "To do in October: " + " · ".join(
            f"prune Plant number {i}, Another plant and 9 more"
            for i in range(40))
        self.addCleanup(month_tasks.refresh, win)
        self.addCleanup(setattr, win, "_month_tasks_key", None)
        label.setText(line)
        self._app.processEvents()
        self.assertEqual(win.minimumSizeHint().width(), before)
        self.assertLessEqual(before, 1366)
        self.assertEqual(label.text(), line)
        painted = QLabel.text(label)
        self.assertTrue(len(painted) > 20 and painted.endswith("…"), painted)
        self.assertTrue(line.startswith(painted[:-1]), painted)
        self.assertEqual(label.toolTip(), line)

    def test_the_pin_instruction_is_said_once(self):
        """R26's other half: the strip, a green box at the top of Site Info
        and a paragraph under it all said how to drop the pin. The strip
        keeps it (its detail line, or its tooltip when the strip is narrow)."""
        from PyQt6.QtWidgets import QLabel
        from src import onboarding, onboarding_flow
        win = self._win
        onboarding_flow.refresh(win)
        step = onboarding.first_step(win._project)
        self.assertEqual(step["key"], "pin")
        bar = win.first_step_bar
        self.assertEqual(bar._detail_text, step["detail"])
        said = [lbl.text() for lbl in win.site_panel.findChildren(QLabel)
                if step["title"] in lbl.text() or step["detail"] in lbl.text()
                or "drop the pin on the map" in lbl.text()]
        self.assertEqual(said, [])

    def test_empty_example_then_new(self):
        from unittest import mock
        from src import onboarding, onboarding_flow
        win = self._win
        self.assertEqual(win._sb_tasks.text(), "")

        example = os.path.join(_TMP_DIR, "example.perma.geojson")
        with mock.patch.object(month_tasks, "date") as today, \
                mock.patch.object(onboarding_flow, "example_path",
                                  return_value=example):
            # A month in which the example has a job, so the line is not
            # empty for the wrong reason.
            month = next(m for m in range(1, 13)
                         if month_tasks.jobs_for(
                             {p["plant_id"] for p in
                              onboarding.resolve_example_planting()[0]}, m))
            today.today.return_value = types.SimpleNamespace(month=month)
            onboarding_flow.open_example(win)
            names = {p["common_name"] for p in win._placed_plants}
            line = win._sb_tasks.text()
            self.assertTrue(line.startswith("To do in "), line)
            words = [w for w, _s in month_tasks.JOBS]
            for part in line.split(": ", 1)[1].split(" · "):
                job = next(w for w in words if part.startswith(w + " "))
                listed = part[len(job) + 1:].split(" and ")[0].split(", ")
                for name in listed:
                    self.assertIn(name, names)

            with mock.patch("src.app.QInputDialog.getText",
                            return_value=("Test yard", True)):
                win._modified = False
                win._on_new()
            self.assertEqual(win._sb_tasks.text(), "")


if __name__ == "__main__":
    unittest.main()
